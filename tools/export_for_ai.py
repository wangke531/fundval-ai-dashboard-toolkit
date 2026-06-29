#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from import_alipay_snapshot import DEFAULT_BASE_URL, DEFAULT_USERNAME, FundValClient, load_dotenv, save_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "exports" / "ai_portfolio_snapshot.json"


def rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("results", "value", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def money(value: Any) -> str | None:
    dec = decimal_or_none(value)
    if dec is None:
        return None
    return str(dec.quantize(Decimal("0.01")))


def pct(value: Any) -> str | None:
    dec = decimal_or_none(value)
    if dec is None:
        return None
    return str((dec * Decimal("100")).quantize(Decimal("0.01")))


def estimate_today_pnl(position: dict[str, Any]) -> str | None:
    fund = position.get("fund") if isinstance(position.get("fund"), dict) else {}
    share = decimal_or_none(position.get("holding_share"))
    latest_nav = decimal_or_none(fund.get("latest_nav"))
    estimate_nav = decimal_or_none(fund.get("estimate_nav"))
    if share is None or latest_nav is None or estimate_nav is None:
        return None
    return money((estimate_nav - latest_nav) * share)


def build_position(row: dict[str, Any], source_by_code: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fund = row.get("fund") if isinstance(row.get("fund"), dict) else {}
    code = str(row.get("fund_code") or fund.get("fund_code") or "").zfill(6)
    cost = decimal_or_none(row.get("holding_cost"))
    pnl = decimal_or_none(row.get("pnl"))
    holding_value = cost + pnl if cost is not None and pnl is not None else None
    estimate_growth = decimal_or_none(fund.get("estimate_growth"))
    source = source_by_code.get(code, {})

    return {
        "fund_code": code,
        "fund_name": row.get("fund_name") or fund.get("fund_name"),
        "fund_type": row.get("fund_type") or fund.get("fund_type"),
        "account_name": row.get("account_name"),
        "holding_share": str(row.get("holding_share") or ""),
        "holding_cost": money(row.get("holding_cost")),
        "holding_value": money(holding_value),
        "holding_profit": money(row.get("pnl")),
        "latest_nav": str(fund.get("latest_nav") or ""),
        "latest_nav_date": fund.get("latest_nav_date"),
        "estimate_nav": str(fund.get("estimate_nav") or ""),
        "estimate_growth_percent": str(estimate_growth) if estimate_growth is not None else None,
        "estimate_today_pnl": estimate_today_pnl(row),
        "estimate_time": fund.get("estimate_time"),
        "estimate_source": fund.get("estimate_source") or source.get("estimate_source"),
        "estimate_source_label": fund.get("estimate_source_label") or source.get("estimate_source_label"),
        "requested_source": fund.get("requested_source") or source.get("requested_source"),
        "is_fallback": fund.get("is_fallback", source.get("is_fallback")),
        "estimate_source_status": fund.get("estimate_source_status") or source.get("status"),
    }


def summarize(accounts: list[dict[str, Any]], positions: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    account = next((row for row in accounts if row.get("parent")), accounts[0] if accounts else {})
    by_source = source_summary.get("counts") if isinstance(source_summary.get("counts"), dict) else {}
    return {
        "account_name": account.get("name"),
        "holding_cost": money(account.get("holding_cost")),
        "holding_value": money(account.get("holding_value")),
        "holding_profit": money(account.get("pnl")),
        "holding_profit_rate_percent": pct(account.get("pnl_rate")),
        "estimate_value": money(account.get("estimate_value")),
        "estimate_profit": money(account.get("estimate_pnl")),
        "estimate_profit_rate_percent": pct(account.get("estimate_pnl_rate")),
        "today_estimate_pnl": money(account.get("today_pnl")),
        "today_estimate_pnl_rate_percent": pct(account.get("today_pnl_rate")),
        "position_count": len(positions),
        "estimate_source_counts": by_source,
        "fallback_count": source_summary.get("fallback_count"),
    }


def export_for_ai(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    password = args.password
    if not password:
        import os

        password = os.environ.get("FUNDVAL_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("--password is required, or set FUNDVAL_ADMIN_PASSWORD in .env")

    client = FundValClient(args.base_url, args.username, password)
    accounts_data = client.request_json("GET", "/api/accounts/")
    positions_data = client.request_json("GET", "/api/positions/")
    source_summary = client.request_json("GET", "/api/local/estimate-sources/")
    preferences = client.request_json("GET", "/api/preferences/")

    accounts = rows(accounts_data)
    source_items = rows(source_summary)
    source_by_code = {str(item.get("fund_code") or "").zfill(6): item for item in source_items}
    positions = [build_position(row, source_by_code) for row in rows(positions_data)]
    positions.sort(key=lambda row: decimal_or_none(row.get("holding_value")) or Decimal("0"), reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "summary": summarize(accounts, positions, source_summary if isinstance(source_summary, dict) else {}),
        "positions": positions,
        "accounts_raw": accounts,
        "preferences": preferences,
        "analysis_notes": [
            "This is structured data exported for AI analysis.",
            "holding_value and holding_profit come from the imported Alipay snapshot plus FundVal-Live calculations.",
            "estimate_today_pnl is an intraday estimate, not an official settled Alipay value.",
            "Do not treat AI output as financial advice.",
        ],
    }
    save_json(Path(args.out), payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export FundVal-Live portfolio data for AI tools.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=None)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> None:
    payload = export_for_ai(parse_args())
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
