"""
Local FundVal-Live estimate source patch.

This keeps the dashboard on the user's Alipay holdings while preferring
YangJiBao estimates. Fallback sources are temporary: when a fund later becomes
available in YangJiBao, the next refresh switches it back automatically.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

_PATCHED = False
_TABLE_READY = False
ACCOUNT_NAME = "Alipay Fund"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
US_TZ = ZoneInfo("America/New_York")
MONEY = Decimal("0.01")
LOCAL_PNL_SERIES = Path("/app/local-history/local_pnl_series.jsonl")
LOCAL_HISTORY_DIR = Path("/app/local-history")
LOCAL_IMPORTS_DIR = Path("/app/local-imports")

LOGIN_SOURCES = {"yangjibao", "xiaobeiyangji"}
SOURCE_LABELS = {
    "yangjibao": "养基宝",
    "eastmoney": "东方财富",
    "sina": "新浪",
    "xiaobeiyangji": "小倍养基",
    "danjuan": "蛋卷",
}


def _decimal(value, default="0"):
    if value is None or value == "":
        if default is None:
            return None
        value = default
    try:
        return Decimal(str(value).replace(",", "").replace("¥", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        if default is None:
            return None
        return Decimal(default)


def _money(value):
    return str(_decimal(value).quantize(MONEY))


def _plain_decimal(value):
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _ratio_percent(value):
    dec = _decimal(value)
    return str((dec * Decimal("100")).quantize(MONEY))


def _previous_weekday(day):
    current = day - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def _date_or_none(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _local_now():
    return timezone.now().astimezone(LOCAL_TZ)


def _local_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.utc)
    return value.astimezone(LOCAL_TZ)


def _day_stage(now):
    today = now.date()
    minutes = now.hour * 60 + now.minute
    if minutes < 15 * 60:
        return {
            "stage": "penetrating",
            "label": "穿透中",
            "range_label": "00:00-14:59",
            "archive_time": "23:59",
            "today_has_started": True,
            "profit_date": today,
        }
    return {
        "stage": "settling",
        "label": "结算中",
        "range_label": "15:00-23:59",
        "archive_time": "23:59",
        "today_has_started": True,
        "profit_date": today,
    }


def _us_stage(now):
    us_now = now.astimezone(US_TZ)
    today = us_now.date()
    current = us_now.time()
    is_weekday = today.weekday() < 5
    regular_open = time(9, 30) <= current < time(16, 0)
    if is_weekday and regular_open:
        label = "美股交易中"
        stage = "trading"
    elif is_weekday and current < time(9, 30):
        label = "美股未开盘"
        stage = "before_open"
    else:
        label = "美股休市/已收盘"
        stage = "closed"
    return {
        "stage": stage,
        "label": label,
        "us_time": us_now.isoformat(),
        "regular_session": bool(is_weekday and regular_open),
    }


def _market_clock(now):
    day_stage = _day_stage(now)
    us = _us_stage(now)
    return {
        "now": now.isoformat(),
        "date": now.date().isoformat(),
        "day_stage": {
            **day_stage,
            "profit_date": day_stage["profit_date"].isoformat(),
        },
        "a_share": {
            "stage": day_stage["stage"],
            "label": day_stage["label"],
            "today_has_started": True,
            "active_trade_date": day_stage["profit_date"].isoformat(),
        },
        "us": us,
    }


def _is_qdii(name, fund_type):
    text = f"{name or ''} {fund_type or ''}".upper()
    keywords = ["QDII", "纳斯达克", "全球", "海外", "标普", "美国", "恒生", "日经"]
    return any(keyword.upper() in text for keyword in keywords)


def _is_fixed_income(name, fund_type):
    text = f"{name or ''} {fund_type or ''}"
    return "债" in text or "货币" in text or "固收" in text


def _fund_bucket(name, fund_type):
    if _is_qdii(name, fund_type):
        return "qdii"
    if _is_fixed_income(name, fund_type):
        return "fixed_income"
    return "domestic"


def _snapshot_candidates():
    candidates = []
    for base in (Path("/app/local-imports"), Path("imports")):
        path = base / "alipay_snapshot.json"
        if path.exists():
            candidates.append(path)
    for base in (Path("/app/local-history"), Path("history")):
        if base.exists():
            candidates.extend(base.glob("*/alipay_snapshot.json"))
    return sorted(set(candidates), key=lambda path: path.stat().st_mtime, reverse=True)


def _position_history_candidates():
    candidates = []
    for base in (LOCAL_HISTORY_DIR, Path("history")):
        if base.exists():
            candidates.extend(base.glob("*/alipay_snapshot.json"))
    for base in (LOCAL_IMPORTS_DIR, Path("imports")):
        path = base / "alipay_snapshot.json"
        if path.exists():
            candidates.append(path)
    return sorted(set(candidates), key=lambda path: str(path))


def _load_latest_alipay_snapshot():
    for path in _snapshot_candidates():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        holdings = data.get("holdings")
        if isinstance(holdings, list) and holdings:
            snapshot_date = _date_or_none(data.get("snapshot_date"))
            by_code = {
                str(item.get("fund_code") or "").zfill(6): item
                for item in holdings
                if item.get("fund_code")
            }
            return {
                "path": str(path),
                "snapshot_date": snapshot_date,
                "account_name": data.get("account_name"),
                "holdings": holdings,
                "by_code": by_code,
                "holding_profit": sum(
                    _decimal(item.get("holding_profit")) for item in holdings
                ),
                "holding_value": sum(
                    _decimal(item.get("holding_value")) for item in holdings
                ),
            }
    return None


def _load_position_history(fund_code):
    code = str(fund_code or "").zfill(6)
    points_by_date = {}
    fund_name = None
    for path in _position_history_candidates():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        snapshot_date = data.get("snapshot_date")
        if not snapshot_date and path.parent.name:
            snapshot_date = path.parent.name
        holdings = data.get("holdings")
        if not snapshot_date or not isinstance(holdings, list):
            continue
        for item in holdings:
            if str(item.get("fund_code") or "").zfill(6) != code:
                continue
            fund_name = item.get("fund_name") or fund_name
            holding_value = _decimal(
                item.get("holding_value")
                or item.get("market_value")
                or item.get("current_value")
                or item.get("amount"),
                default=None,
            )
            holding_profit = _decimal(
                item.get("holding_profit") or item.get("profit") or item.get("pnl"),
                default=None,
            )
            share = _decimal(item.get("share"), default=None)
            nav = _decimal(item.get("nav") or item.get("latest_nav"), default=None)
            points_by_date[str(snapshot_date)] = {
                "date": str(snapshot_date),
                "source": "alipay_snapshot",
                "snapshot_file": str(path),
                "fund_code": code,
                "fund_name": item.get("fund_name") or fund_name,
                "holding_value": _money(holding_value) if holding_value is not None else "",
                "holding_profit": _money(holding_profit) if holding_profit is not None else "",
                "share": _plain_decimal(share) if share is not None else str(item.get("share") or ""),
                "nav": _plain_decimal(nav) if nav is not None else str(item.get("nav") or item.get("latest_nav") or ""),
                "_holding_value_decimal": holding_value,
                "_holding_profit_decimal": holding_profit,
                "_share_decimal": share,
                "_nav_decimal": nav,
            }
    points = [points_by_date[key] for key in sorted(points_by_date)]
    previous = None
    for point in points:
        if previous is None:
            point["change_label"] = "首次记录"
            point["share_delta"] = ""
            point["holding_value_delta"] = ""
            point["holding_profit_delta"] = ""
            point["nav_delta"] = ""
        else:
            share = point.get("_share_decimal")
            previous_share = previous.get("_share_decimal")
            if share is not None and previous_share is not None:
                share_delta = share - previous_share
                point["share_delta"] = _plain_decimal(share_delta)
                if share_delta > 0:
                    point["change_label"] = "加仓"
                elif share_delta < 0:
                    point["change_label"] = "减仓"
                else:
                    point["change_label"] = "份额不变"
            else:
                point["share_delta"] = ""
                point["change_label"] = "份额缺失"

            holding_value = point.get("_holding_value_decimal")
            previous_holding_value = previous.get("_holding_value_decimal")
            if holding_value is not None and previous_holding_value is not None:
                point["holding_value_delta"] = _money(holding_value - previous_holding_value)
            else:
                point["holding_value_delta"] = ""

            holding_profit = point.get("_holding_profit_decimal")
            previous_holding_profit = previous.get("_holding_profit_decimal")
            if holding_profit is not None and previous_holding_profit is not None:
                point["holding_profit_delta"] = _money(holding_profit - previous_holding_profit)
            else:
                point["holding_profit_delta"] = ""

            nav = point.get("_nav_decimal")
            previous_nav = previous.get("_nav_decimal")
            point["nav_delta"] = _plain_decimal(nav - previous_nav) if nav is not None and previous_nav is not None else ""

        previous = point
        for key in ("_holding_value_decimal", "_holding_profit_decimal", "_share_decimal", "_nav_decimal"):
            point.pop(key, None)
    return {
        "fund_code": code,
        "fund_name": fund_name,
        "point_count": len(points),
        "points": points,
        "note": "支付宝截图只用于记录持仓市值、份额和持有收益基准；折线图不读取支付宝昨日收益。",
    }


def _json_default(value):
    if isinstance(value, Decimal):
        return _money(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_jsonl(path, rows):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n" for row in rows),
            encoding="utf-8",
        )
    except Exception:
        pass


def _upsert_pnl_series(row):
    rows = _read_jsonl(LOCAL_PNL_SERIES)
    key = row.get("date")
    replaced = False
    next_rows = []
    for existing in rows:
        if existing.get("date") == key:
            next_rows.append(row)
            replaced = True
        else:
            next_rows.append(existing)
    if not replaced:
        next_rows.append(row)
    next_rows.sort(key=lambda item: item.get("date") or "")
    _write_jsonl(LOCAL_PNL_SERIES, next_rows)
    return next_rows


def _build_snapshot_baseline_rows(snapshot):
    if not snapshot or not snapshot.get("snapshot_date"):
        return []
    snapshot_date = snapshot["snapshot_date"]
    snapshot_profit = snapshot["holding_profit"]
    return [
        {
            "date": snapshot_date.isoformat(),
            "kind": "snapshot_base",
            "label": "持仓快照基准",
            "daily_profit": None,
            "estimated_total_profit": _money(snapshot_profit),
            "source": "position_snapshot",
            "note": "支付宝截图只用于同步持仓、成本和持有收益基准，不使用支付宝显示的昨日收益。",
        },
    ]


def _series_with_deltas(rows):
    ordered = sorted(rows, key=lambda item: item.get("date") or "")
    previous_profit = None
    result = []
    for row in ordered:
        item = dict(row)
        total = _decimal(item.get("estimated_total_profit"), None)
        explicit_daily = item.get("daily_profit")
        if explicit_daily in (None, "") and previous_profit is not None and total is not None:
            item["daily_profit"] = _money(total - previous_profit)
        if total is not None:
            previous_profit = total
        result.append(item)
    return result


def _position_numbers(position, snapshot_item, market):
    fund = position.fund
    name = fund.fund_name
    fund_type = fund.fund_type
    bucket = _fund_bucket(name, fund_type)
    share = _decimal(position.holding_share)
    cost = _decimal(position.holding_cost)
    latest_nav = _decimal(fund.latest_nav)
    estimate_nav = _decimal(fund.estimate_nav)
    estimate_growth = _decimal(fund.estimate_growth, None) if fund.estimate_growth is not None else None
    holding_value = share * latest_nav if latest_nav else Decimal("0")
    current_profit = holding_value - cost
    estimate_delta = (
        (estimate_nav - latest_nav) * share
        if share and latest_nav and estimate_nav
        else Decimal("0")
    )
    growth_delta = (
        latest_nav * share * estimate_growth / Decimal("100")
        if share and latest_nav and estimate_growth is not None
        else Decimal("0")
    )
    snapshot_profit = _decimal((snapshot_item or {}).get("holding_profit"))
    settled_delta = current_profit - snapshot_profit if snapshot_item else Decimal("0")
    estimate_time = _local_datetime(fund.estimate_time)
    profit_date = market.get("profit_date") or market.get("date")
    estimate_is_current = bool(
        estimate_time and profit_date and estimate_time.date() >= profit_date
    )
    effective_estimate_delta = estimate_delta if estimate_is_current else Decimal("0")
    effective_growth_delta = growth_delta if estimate_is_current else Decimal("0")
    today_live_delta = (
        effective_growth_delta
        if estimate_growth is not None and estimate_is_current
        else effective_estimate_delta
    )

    return {
        "fund_code": fund.fund_code,
        "fund_name": name,
        "fund_type": fund_type,
        "bucket": bucket,
        "holding_share": str(position.holding_share),
        "holding_cost": _money(cost),
        "holding_value": _money(holding_value),
        "current_holding_profit": _money(current_profit),
        "snapshot_holding_profit": _money(snapshot_profit),
        "settled_delta_since_snapshot": _money(settled_delta),
        "estimate_delta": _money(effective_estimate_delta),
        "growth_delta_reference": _money(effective_growth_delta),
        "today_live_delta": _money(today_live_delta),
        "estimated_delta_since_snapshot": _money(
            settled_delta + effective_estimate_delta
        ),
        "latest_nav": str(fund.latest_nav or ""),
        "latest_nav_date": fund.latest_nav_date.isoformat() if fund.latest_nav_date else None,
        "estimate_nav": str(fund.estimate_nav or ""),
        "estimate_growth_percent": str(fund.estimate_growth or ""),
        "estimate_time": estimate_time.isoformat() if estimate_time else None,
        "estimate_is_current": estimate_is_current,
    }


def _ensure_meta_table():
    global _TABLE_READY
    if _TABLE_READY:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS local_estimate_source_meta (
                fund_code varchar(10) PRIMARY KEY,
                requested_source varchar(50),
                estimate_source varchar(50),
                fallback_source varchar(50),
                is_fallback boolean NOT NULL DEFAULT false,
                status varchar(50),
                error text,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    _TABLE_READY = True


def _read_meta(fund_codes):
    _ensure_meta_table()
    codes = list(dict.fromkeys(fund_codes))
    if not codes:
        return {}
    placeholders = ",".join(["%s"] * len(codes))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT fund_code, requested_source, estimate_source, fallback_source,
                   is_fallback, status, error, updated_at
            FROM local_estimate_source_meta
            WHERE fund_code IN ({placeholders})
            """,
            codes,
        )
        rows = cursor.fetchall()
    return {
        row[0]: {
            "requested_source": row[1],
            "estimate_source": row[2],
            "fallback_source": row[3],
            "is_fallback": row[4],
            "status": row[5],
            "error": row[6],
            "updated_at": row[7],
        }
        for row in rows
    }


def _write_meta(
    fund_code,
    requested_source,
    estimate_source,
    fallback_source=None,
    is_fallback=False,
    status_text="ok",
    error_text=None,
):
    _ensure_meta_table()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO local_estimate_source_meta (
                fund_code, requested_source, estimate_source, fallback_source,
                is_fallback, status, error, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (fund_code) DO UPDATE SET
                requested_source = EXCLUDED.requested_source,
                estimate_source = EXCLUDED.estimate_source,
                fallback_source = EXCLUDED.fallback_source,
                is_fallback = EXCLUDED.is_fallback,
                status = EXCLUDED.status,
                error = EXCLUDED.error,
                updated_at = now()
            """,
            [
                fund_code,
                requested_source,
                estimate_source,
                fallback_source,
                is_fallback,
                status_text,
                error_text,
            ],
        )


def _source_label(source_name):
    return SOURCE_LABELS.get(source_name or "", source_name or "未知")


def _credential_for(source_name, user):
    from api.models import UserSourceCredential

    credential = None
    if getattr(user, "is_authenticated", False):
        credential = UserSourceCredential.objects.filter(
            user=user, source_name=source_name, is_active=True
        ).first()
    if not credential:
        credential = UserSourceCredential.objects.filter(
            source_name=source_name, is_active=True
        ).first()
    return credential


def _get_source(source_name, user):
    from api.sources.registry import SourceRegistry

    source = SourceRegistry.get_source(source_name)
    if not source:
        return None
    if source_name in LOGIN_SOURCES:
        credential = _credential_for(source_name, user)
        if not credential:
            raise RuntimeError(f"{_source_label(source_name)}未登录")
        if hasattr(source, "set_token"):
            source.set_token(credential.token)
        else:
            source._token = credential.token
    return source


def _fetch_estimate(source_name, fund_code, user):
    source = _get_source(source_name, user)
    if not source:
        raise RuntimeError(f"数据源不存在: {source_name}")
    return source.fetch_estimate(fund_code)


def _preferred_source(request, requested_source):
    if requested_source:
        return requested_source
    if getattr(request.user, "is_authenticated", False):
        try:
            from api.models import UserPreference

            pref = UserPreference.objects.filter(user=request.user).first()
            if pref and pref.preferred_source:
                return pref.preferred_source
        except Exception:
            pass
    return "yangjibao"


def _source_chain(primary, fallback):
    if primary == "danjuan":
        primary = "eastmoney"
    chain = [primary]
    if primary != "eastmoney" and fallback and fallback not in chain:
        chain.append(fallback)
    return chain


def _cache_matches_request(meta, requested_source):
    actual_source = (meta or {}).get("estimate_source")
    if actual_source:
        return actual_source == requested_source
    return requested_source == "eastmoney"


def _build_result(code, fund, meta, from_cache):
    source_name = (meta or {}).get("estimate_source")
    return {
        "fund_code": code,
        "fund_name": fund.fund_name,
        "estimate_nav": str(fund.estimate_nav) if fund.estimate_nav else None,
        "estimate_growth": str(fund.estimate_growth) if fund.estimate_growth else None,
        "estimate_time": fund.estimate_time.isoformat() if fund.estimate_time else None,
        "latest_nav": str(fund.latest_nav) if fund.latest_nav else None,
        "latest_nav_date": (
            fund.latest_nav_date.isoformat() if fund.latest_nav_date else None
        ),
        "from_cache": from_cache,
        "estimate_source": source_name,
        "estimate_source_label": _source_label(source_name),
        "requested_source": (meta or {}).get("requested_source"),
        "is_fallback": bool((meta or {}).get("is_fallback")),
        "estimate_source_status": (meta or {}).get("status"),
    }


def _patched_batch_estimate(original):
    @wraps(original)
    def batch_estimate(self, request):
        from api.models import Fund
        from fundval.config import config

        fund_codes = request.data.get("fund_codes", [])
        requested_source = _preferred_source(request, request.data.get("source"))
        fallback_source = request.data.get("fallback_source", "eastmoney")
        ttl_minutes = config.get("estimate_cache_ttl", 5)

        if not fund_codes:
            return Response(
                {"error": "缺少 fund_codes 参数"}, status=status.HTTP_400_BAD_REQUEST
            )

        funds = Fund.objects.filter(fund_code__in=fund_codes)
        fund_map = {f.fund_code: f for f in funds}
        meta_map = _read_meta(fund_codes)

        results = {}
        need_fetch = []
        now = timezone.now()
        for code in fund_codes:
            fund = fund_map.get(code)
            if not fund:
                results[code] = {"error": "基金不存在"}
                continue

            meta = meta_map.get(code)
            cache_fresh = (
                fund.estimate_nav
                and fund.estimate_time
                and (now - fund.estimate_time).total_seconds() < ttl_minutes * 60
            )
            if cache_fresh and _cache_matches_request(meta, requested_source):
                results[code] = _build_result(code, fund, meta, from_cache=True)
            else:
                need_fetch.append(code)

        chain = _source_chain(requested_source, fallback_source)

        def fetch_for_code(code):
            errors = []
            for source_name in chain:
                try:
                    data = _fetch_estimate(source_name, code, request.user)
                    if data:
                        return source_name, data, errors
                    errors.append(f"{_source_label(source_name)}无估值")
                except Exception as exc:
                    errors.append(f"{_source_label(source_name)}: {exc}")
            return None, None, errors

        if need_fetch:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(fetch_for_code, code): code for code in need_fetch
                }
                for future in as_completed(futures):
                    code = futures[future]
                    fund = fund_map.get(code)
                    try:
                        actual_source, data, errors = future.result()
                        if fund and data and actual_source:
                            fund.estimate_nav = data.get("estimate_nav")
                            fund.estimate_growth = data.get("estimate_growth")
                            fund.estimate_time = timezone.now()
                            fund.save(
                                update_fields=[
                                    "estimate_nav",
                                    "estimate_growth",
                                    "estimate_time",
                                ]
                            )
                            is_fallback = actual_source != requested_source
                            _write_meta(
                                code,
                                requested_source=requested_source,
                                estimate_source=actual_source,
                                fallback_source=actual_source if is_fallback else None,
                                is_fallback=is_fallback,
                                status_text="fallback" if is_fallback else "ok",
                                error_text="; ".join(errors) if errors else None,
                            )
                            meta = _read_meta([code]).get(code)
                            results[code] = _build_result(
                                code, fund, meta, from_cache=False
                            )
                        else:
                            _write_meta(
                                code,
                                requested_source=requested_source,
                                estimate_source=None,
                                fallback_source=fallback_source,
                                is_fallback=False,
                                status_text="error",
                                error_text="; ".join(errors),
                            )
                            results[code] = {
                                "fund_code": code,
                                "error": "获取估值失败: " + "; ".join(errors),
                            }
                    except Exception as exc:
                        results[code] = {
                            "fund_code": code,
                            "error": f"获取估值失败: {exc}",
                        }

        return Response(results)

    for attr in ("mapping", "detail", "url_path", "url_name", "kwargs"):
        if hasattr(original, attr):
            setattr(batch_estimate, attr, getattr(original, attr))
    return batch_estimate


def _patch_serializers():
    from api.serializers import PositionSerializer

    if getattr(PositionSerializer, "_local_source_patched", False):
        return
    original_get_fund = PositionSerializer.get_fund

    def get_fund(self, obj):
        data = original_get_fund(self, obj)
        meta = _read_meta([obj.fund.fund_code]).get(obj.fund.fund_code, {})
        source_name = meta.get("estimate_source")
        data.update(
            {
                "estimate_source": source_name,
                "estimate_source_label": _source_label(source_name),
                "requested_source": meta.get("requested_source"),
                "is_fallback": bool(meta.get("is_fallback")),
                "estimate_source_status": meta.get("status"),
            }
        )
        return data

    PositionSerializer.get_fund = get_fund
    PositionSerializer._local_source_patched = True


def _patch_viewsets():
    from api.viewsets import FundViewSet

    if getattr(FundViewSet, "_local_estimate_patched", False):
        return
    FundViewSet.batch_estimate = _patched_batch_estimate(FundViewSet.batch_estimate)
    FundViewSet._local_estimate_patched = True


def apply_patch_once():
    global _PATCHED
    if _PATCHED:
        return
    _ensure_meta_table()
    _patch_serializers()
    _patch_viewsets()
    _PATCHED = True


def estimate_source_summary():
    apply_patch_once()
    from api.models import Position

    positions = list(Position.objects.select_related("fund", "account").all())
    meta = _read_meta([p.fund.fund_code for p in positions])
    counts = {}
    fallback_count = 0
    items = []
    for pos in positions:
        fund_code = pos.fund.fund_code
        item_meta = meta.get(fund_code, {})
        source_name = item_meta.get("estimate_source")
        label = _source_label(source_name)
        counts[label] = counts.get(label, 0) + 1
        if item_meta.get("is_fallback"):
            fallback_count += 1
        items.append(
            {
                "fund_code": fund_code,
                "fund_name": pos.fund.fund_name,
                "estimate_source": source_name,
                "estimate_source_label": label,
                "requested_source": item_meta.get("requested_source"),
                "is_fallback": bool(item_meta.get("is_fallback")),
                "status": item_meta.get("status"),
                "error": item_meta.get("error"),
            }
        )
    return {
        "count": len(items),
        "counts": counts,
        "fallback_count": fallback_count,
        "items": items,
    }


def pnl_summary():
    apply_patch_once()
    from api.models import Account, Position

    now = _local_now()
    market = _market_clock(now)
    snapshot = _load_latest_alipay_snapshot()
    account = Account.objects.filter(name=ACCOUNT_NAME).first()
    if not account:
        account = Account.objects.filter(parent__isnull=False).first()
    if not account:
        return {"error": "account not found"}

    positions = list(
        Position.objects.select_related("fund", "account")
        .filter(account=account)
        .order_by("fund__fund_code")
    )
    meta = _read_meta([p.fund.fund_code for p in positions])
    snapshot_by_code = snapshot["by_code"] if snapshot else {}
    market_dates = {
        "date": date.fromisoformat(market["date"]),
        "profit_date": date.fromisoformat(market["day_stage"]["profit_date"]),
    }
    items = []
    for position in positions:
        item = _position_numbers(
            position,
            snapshot_by_code.get(position.fund.fund_code),
            {
                **market,
                "date": market_dates["date"],
                "profit_date": market_dates["profit_date"],
            },
        )
        item_meta = meta.get(position.fund.fund_code, {})
        source_name = item_meta.get("estimate_source")
        item.update(
            {
                "estimate_source": source_name,
                "estimate_source_label": _source_label(source_name),
                "requested_source": item_meta.get("requested_source"),
                "is_fallback": bool(item_meta.get("is_fallback")),
            }
        )
        items.append(item)

    current_holding_profit = sum(_decimal(item["current_holding_profit"]) for item in items)
    current_holding_value = sum(_decimal(item["holding_value"]) for item in items)
    current_holding_cost = sum(_decimal(item["holding_cost"]) for item in items)
    settled_delta = sum(_decimal(item["settled_delta_since_snapshot"]) for item in items)
    estimate_delta = sum(_decimal(item["estimate_delta"]) for item in items)
    today_live_delta = sum(_decimal(item["today_live_delta"]) for item in items)
    qdii_live_reference = sum(
        _decimal(item["today_live_delta"]) for item in items if item["bucket"] == "qdii"
    )
    domestic_live_delta = sum(
        _decimal(item["today_live_delta"]) for item in items if item["bucket"] != "qdii"
    )
    estimate_total_profit = current_holding_profit + estimate_delta
    snapshot_profit = snapshot["holding_profit"] if snapshot else Decimal("0")
    estimated_delta_since_snapshot = estimate_total_profit - snapshot_profit

    nav_counts = {}
    for item in items:
        key = item["latest_nav_date"] or "未知"
        nav_counts[key] = nav_counts.get(key, 0) + 1
    source_counts = {}
    fallback_count = 0
    for item in items:
        label = item.get("estimate_source_label") or item.get("estimate_source") or "未知"
        source_counts[label] = source_counts.get(label, 0) + 1
        if item.get("is_fallback"):
            fallback_count += 1

    snapshot_date = snapshot["snapshot_date"] if snapshot else None
    profit_date = market_dates["profit_date"]
    settlement_complete = all(
        (_date_or_none(item["latest_nav_date"]) or date.min) >= profit_date
        for item in items
        if item["bucket"] != "qdii"
    )
    if market["day_stage"]["stage"] == "settling":
        settlement_label = "结算中，跟随养基宝实时变化，23:59 归档为当日收益"
    else:
        settlement_label = "穿透中，跟随养基宝实时变化"

    items.sort(
        key=lambda item: abs(_decimal(item["estimated_delta_since_snapshot"])),
        reverse=True,
    )

    baseline_rows = _build_snapshot_baseline_rows(snapshot)
    current_series_row = {
        "date": profit_date.isoformat(),
        "kind": "yangjibao_estimated_day",
        "label": f"养基宝估算当日收益（{market['day_stage']['label']}）",
        "daily_profit": _money(today_live_delta),
        "estimated_total_profit": _money(estimate_total_profit),
        "settled_delta": _money(settled_delta),
        "unsettled_estimate_delta": _money(estimate_delta),
        "baseline_delta_since_snapshot": _money(estimated_delta_since_snapshot),
        "source": "yangjibao_plus_nav",
        "generated_at": now.isoformat(),
        "stage": market["day_stage"]["stage"],
        "note": "按北京时间自然日、当前持仓和养基宝/净值变化计算；23:59 作为当日收益归档点。",
    }
    archived_series_rows = _read_jsonl(LOCAL_PNL_SERIES)
    if not archived_series_rows and baseline_rows:
        archived_series_rows = baseline_rows
        _write_jsonl(LOCAL_PNL_SERIES, archived_series_rows)
    display_series_rows = [
        row
        for row in archived_series_rows
        if row.get("date") != current_series_row["date"]
    ]
    display_series_rows.append({**current_series_row, "transient": True})
    series_rows = _series_with_deltas(display_series_rows)

    daily_pnl = {
        "date": profit_date.isoformat(),
        "daily_profit": _money(today_live_delta),
        "domestic_delta": _money(domestic_live_delta),
        "qdii_delta_reference": _money(qdii_live_reference),
        "stage": market["day_stage"]["stage"],
        "stage_label": market["day_stage"]["label"],
        "range_label": market["day_stage"].get("range_label"),
        "archive_time": market["day_stage"].get("archive_time"),
        "settlement_label": settlement_label,
        "settlement_complete": settlement_complete,
        "note": "北京时间自然日收益；凌晨美股和白天 A 股都归入当天，刷新时跟随养基宝实时重算，23:59 固化为当日收益。",
    }

    return {
        "generated_at": now.isoformat(),
        "account_name": account.name,
        "position_count": len(items),
        "market_clock": market,
        "latest_alipay_snapshot": {
            "path": snapshot["path"] if snapshot else None,
            "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
            "holding_profit": _money(snapshot_profit),
            "holding_value": _money(snapshot["holding_value"] if snapshot else Decimal("0")),
            "usage": "position_snapshot_only",
        },
        "last_closed_trade": {
            "date": profit_date.isoformat(),
            "daily_profit": _money(today_live_delta),
            "settled_delta": _money(settled_delta),
            "unsettled_estimate_delta": _money(estimate_delta),
            "baseline_delta_since_snapshot": _money(estimated_delta_since_snapshot),
            "snapshot_base_profit": _money(snapshot_profit),
            "current_estimated_total_profit": _money(estimate_total_profit),
            "settlement_complete": settlement_complete,
            "settlement_label": settlement_label,
        },
        "daily_pnl": daily_pnl,
        "today_live": {
            "date": market["date"],
            "estimated_profit": _money(today_live_delta),
            "domestic_delta": _money(domestic_live_delta),
            "qdii_delta_reference": _money(qdii_live_reference),
            "label": f"{market['day_stage']['label']} / 跟随养基宝实时变化",
        },
        "current_portfolio": {
            "holding_cost": _money(current_holding_cost),
            "holding_value": _money(current_holding_value),
            "holding_profit": _money(current_holding_profit),
            "holding_profit_rate_percent": _ratio_percent(
                current_holding_profit / current_holding_cost
                if current_holding_cost
                else Decimal("0")
            ),
            "estimate_total_profit": _money(estimate_total_profit),
            "estimate_total_value": _money(current_holding_cost + estimate_total_profit),
        },
        "quality": {
            "nav_date_counts": nav_counts,
            "estimate_source_counts": source_counts,
            "fallback_count": fallback_count,
            "has_snapshot": bool(snapshot),
            "pnl_series_path": str(LOCAL_PNL_SERIES),
        },
        "pnl_series": series_rows[-10:],
        "positions": items,
    }


def position_history(request):
    fund_code = request.GET.get("fund_code") or request.GET.get("code")
    if not fund_code:
        return {"error": "fund_code is required", "points": []}
    return _load_position_history(fund_code)


class LocalEstimatePatchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        apply_patch_once()

    def __call__(self, request):
        if request.path == "/api/local/estimate-sources/":
            return JsonResponse(estimate_source_summary(), json_dumps_params={"ensure_ascii": False})
        if request.path == "/api/local/pnl-summary/":
            return JsonResponse(pnl_summary(), json_dumps_params={"ensure_ascii": False})
        if request.path == "/api/local/position-history/":
            return JsonResponse(position_history(request), json_dumps_params={"ensure_ascii": False})
        return self.get_response(request)
