#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from import_alipay_snapshot import DEFAULT_ACCOUNT_NAME, DEFAULT_USERNAME, FundValClient, load_dotenv


DEFAULT_BASE_URL = "http://localhost:21345"
ROOT = Path(__file__).resolve().parents[1]


def rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("results", "value", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def iter_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for account in accounts:
        flattened.append(account)
        for child in account.get("children") or []:
            if isinstance(child, dict):
                flattened.append(child)
    return flattened


def find_account(accounts: list[dict[str, Any]], account_name: str | None) -> dict[str, Any]:
    flattened = iter_accounts(accounts)
    if account_name:
        for account in flattened:
            if account.get("name") == account_name:
                return account
        raise ValueError(f"account not found: {account_name}")
    for account in flattened:
        if account.get("parent"):
            return account
    if flattened:
        return flattened[0]
    return {}


def position_belongs_to_account(row: dict[str, Any], account: dict[str, Any]) -> bool:
    account_id = str(account.get("id") or "")
    account_name = account.get("name")
    if account_id and str(row.get("account") or "") == account_id:
        return True
    return bool(account_name and row.get("account_name") == account_name)


def refresh_estimates(client: FundValClient, account_name: str, source: str) -> dict[str, Any]:
    accounts_data = client.request_json("GET", "/api/accounts/")
    positions_data = client.request_json("GET", "/api/positions/")
    account = find_account(rows(accounts_data), account_name)
    fund_codes = sorted(
        {
            str(row.get("fund_code") or "").zfill(6)
            for row in rows(positions_data)
            if position_belongs_to_account(row, account) and row.get("fund_code")
        }
    )
    if not fund_codes:
        return {"fund_codes": [], "result": None}
    result = client.update_estimates(fund_codes, source)
    return {"fund_codes": fund_codes, "result": result}


def fetch_summary(client: FundValClient) -> dict[str, Any]:
    return client.request_json("GET", "/api/local/pnl-summary/")


def local_pnl_series_path(summary: dict[str, Any]) -> Path:
    raw_path = ((summary.get("quality") or {}).get("pnl_series_path") or "").replace("\\", "/")
    if raw_path.startswith("/app/local-history/"):
        return ROOT / "history" / raw_path.removeprefix("/app/local-history/")
    return ROOT / "history" / "local_pnl_series.jsonl"


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("date") != row.get("date"):
                rows.append(item)
    rows.append(row)
    rows.sort(key=lambda item: item.get("date") or "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in rows),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive the current local YangJiBao PnL summary."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=None)
    parser.add_argument("--account", default=DEFAULT_ACCOUNT_NAME)
    parser.add_argument("--estimate-source", default="yangjibao")
    parser.add_argument("--skip-refresh", action="store_true", help="Archive the current API value without refreshing estimates first.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    if not args.password:
        import os

        args.password = os.environ.get("FUNDVAL_ADMIN_PASSWORD")
    if not args.password:
        raise SystemExit("--password is required, or set FUNDVAL_ADMIN_PASSWORD in .env")

    client = FundValClient(args.base_url, args.username, args.password)
    refresh = None
    if not args.skip_refresh:
        refresh = refresh_estimates(client, args.account, args.estimate_source)
    summary = fetch_summary(client)
    daily_pnl = summary.get("daily_pnl") or {}
    archive_row = {
        "date": daily_pnl.get("date"),
        "kind": "yangjibao_estimated_day",
        "label": f"养基宝估算当日收益（{daily_pnl.get('stage_label') or ''}）",
        "daily_profit": daily_pnl.get("daily_profit") or (summary.get("last_closed_trade") or {}).get("daily_profit"),
        "estimated_total_profit": (summary.get("current_portfolio") or {}).get("estimate_total_profit"),
        "settled_delta": (summary.get("last_closed_trade") or {}).get("settled_delta"),
        "unsettled_estimate_delta": (summary.get("last_closed_trade") or {}).get("unsettled_estimate_delta"),
        "baseline_delta_since_snapshot": (summary.get("last_closed_trade") or {}).get("baseline_delta_since_snapshot"),
        "source": "yangjibao_plus_nav",
        "generated_at": summary.get("generated_at"),
        "stage": daily_pnl.get("stage"),
        "note": "按北京时间自然日、当前持仓和养基宝/净值变化计算；23:59 作为当日收益归档点。",
    }
    if archive_row.get("date"):
        upsert_jsonl(local_pnl_series_path(summary), archive_row)
    payload = {
        "generated_at": summary.get("generated_at"),
        "refreshed": refresh,
        "stage": (summary.get("market_clock") or {}).get("day_stage"),
        "snapshot": summary.get("latest_alipay_snapshot"),
        "daily_profit": daily_pnl.get("daily_profit") or (summary.get("last_closed_trade") or {}).get("daily_profit"),
        "daily_pnl": daily_pnl,
        "today_live": summary.get("today_live"),
        "pnl_series_path": (summary.get("quality") or {}).get("pnl_series_path"),
        "archived_row": archive_row,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
