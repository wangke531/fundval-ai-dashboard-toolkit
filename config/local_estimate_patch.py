"""
Local FundVal-Live estimate source patch.

This keeps the dashboard on the user's Alipay holdings while preferring
YangJiBao estimates. Fallback sources are temporary: when a fund later becomes
available in YangJiBao, the next refresh switches it back automatically.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

_PATCHED = False
_TABLE_READY = False

LOGIN_SOURCES = {"yangjibao", "xiaobeiyangji"}
SOURCE_LABELS = {
    "yangjibao": "养基宝",
    "eastmoney": "东方财富",
    "sina": "新浪",
    "xiaobeiyangji": "小倍养基",
    "danjuan": "蛋卷",
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

    positions = list(Position.objects.select_related("fund").all())
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


class LocalEstimatePatchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        apply_patch_once()

    def __call__(self, request):
        if request.path == "/api/local/estimate-sources/":
            return JsonResponse(estimate_source_summary(), json_dumps_params={"ensure_ascii": False})
        return self.get_response(request)
