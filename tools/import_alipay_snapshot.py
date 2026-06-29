#!/usr/bin/env python3
"""
Import an Alipay fund holding snapshot into FundVal-Live.

This script treats an Alipay screenshot/OCR result as the source of truth for the
current holding snapshot, then creates synthetic FundVal-Live BUY operations so
the dashboard matches the snapshot. It does not try to reconstruct historical
trades from screenshots.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib import parse, request, error


DEFAULT_BASE_URL = "http://localhost:21345"
DEFAULT_USERNAME = "admin"
DEFAULT_ACCOUNT_NAME = "Alipay Fund"

QTY = Decimal("0.0001")
MONEY = Decimal("0.01")
NAV = Decimal("0.0001")


class FundValError(RuntimeError):
    pass


def D(value: Any, default: str | None = None) -> Decimal:
    if value is None or value == "":
        if default is None:
            raise ValueError("missing decimal value")
        value = default
    if isinstance(value, Decimal):
        return value
    text = str(value).replace(",", "").replace("¥", "").strip()
    return Decimal(text)


def q(value: Decimal, unit: Decimal) -> Decimal:
    return value.quantize(unit, rounding=ROUND_HALF_UP)


def today_iso() -> str:
    return date.today().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass
class FundValClient:
    base_url: str
    username: str
    password: str
    token: str | None = None

    def url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> Any:
        headers = {"Content-Type": "application/json"}
        if auth:
            if not self.token:
                self.login()
            headers["Authorization"] = f"Bearer {self.token}"

        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(self.url(path), data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise FundValError(f"{method} {path} failed: HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise FundValError(f"{method} {path} failed: {exc}") from exc

    def login(self) -> None:
        data = self.request_json(
            "POST",
            "/api/auth/login",
            {"username": self.username, "password": self.password},
            auth=False,
        )
        token = data.get("access_token") or data.get("access")
        if not token:
            raise FundValError(f"login response did not include an access token: {data}")
        self.token = token

    def get_accounts(self) -> list[dict[str, Any]]:
        data = self.request_json("GET", "/api/accounts/")
        if isinstance(data, list):
            return data
        return data.get("results") or data.get("value") or data

    def find_account_id(self, account_name: str) -> str:
        for account in self.get_accounts():
            if account.get("name") == account_name:
                return account["id"]
            for child in account.get("children") or []:
                if child.get("name") == account_name:
                    return child["id"]
        raise FundValError(f"account not found: {account_name}")

    def get_fund(self, fund_code: str) -> dict[str, Any]:
        query = parse.urlencode({"search": fund_code})
        data = self.request_json("GET", f"/api/funds/?{query}")
        for fund in data.get("results") or []:
            if fund.get("fund_code") == fund_code:
                return fund
        raise FundValError(f"fund not found: {fund_code}")

    def update_navs(self, fund_codes: list[str]) -> dict[str, Any]:
        return self.request_json(
            "POST", "/api/funds/batch_update_nav/", {"fund_codes": fund_codes}, auth=False
        )

    def update_estimates(self, fund_codes: list[str], source: str) -> dict[str, Any]:
        return self.request_json(
            "POST",
            "/api/funds/batch_estimate/",
            {"fund_codes": fund_codes, "source": source},
            auth=False,
        )

    def list_operations(self, account_id: str) -> list[dict[str, Any]]:
        query = parse.urlencode({"account": account_id})
        data = self.request_json("GET", f"/api/positions/operations/?{query}")
        if isinstance(data, list):
            return data
        return data.get("results") or data.get("value") or data

    def delete_operation(self, operation_id: str) -> None:
        self.request_json("DELETE", f"/api/positions/operations/{operation_id}/")

    def create_operation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/api/positions/operations/", payload)


def normalize_snapshot(snapshot: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    snapshot_date = snapshot.get("snapshot_date") or today_iso()
    holdings = snapshot.get("holdings")
    if not isinstance(holdings, list) or not holdings:
        raise ValueError("snapshot must include a non-empty holdings list")
    return snapshot_date, holdings


def detect_account_name(snapshot: dict[str, Any], override: str | None) -> str:
    return override or snapshot.get("account_name") or DEFAULT_ACCOUNT_NAME


def calculate_synthetic_buy(
    item: dict[str, Any],
    fund: dict[str, Any],
    snapshot_date: str,
) -> dict[str, Any]:
    fund_code = str(item["fund_code"]).zfill(6)

    holding_value = D(
        item.get("holding_value")
        or item.get("market_value")
        or item.get("current_value")
        or item.get("amount")
    )
    profit = D(item.get("holding_profit") or item.get("profit") or item.get("pnl"), "0")
    cost = q(holding_value - profit, MONEY)

    nav_value = item.get("nav") or item.get("latest_nav") or fund.get("latest_nav")
    if nav_value is None:
        raise ValueError(f"{fund_code}: missing nav/latest_nav")
    nav_decimal = q(D(nav_value), NAV)
    if nav_decimal <= 0:
        raise ValueError(f"{fund_code}: nav must be positive")

    if item.get("share"):
        share = q(D(item["share"]), QTY)
    else:
        share = q(holding_value / nav_decimal, QTY)

    if share <= 0:
        raise ValueError(f"{fund_code}: share must be positive")

    if cost <= 0:
        raise ValueError(f"{fund_code}: synthetic cost must be positive")

    operation_nav = q(cost / share, NAV)

    return {
        "fund_code": fund_code,
        "operation_type": "BUY",
        "operation_date": item.get("operation_date") or snapshot_date,
        "before_15": bool(item.get("before_15", True)),
        "amount": str(cost),
        "share": str(share),
        "nav": str(operation_nav),
        "source_holding_value": str(q(holding_value, MONEY)),
        "source_profit": str(q(profit, MONEY)),
        "source_fund_name": item.get("fund_name"),
    }


def operation_matches_fund(op: dict[str, Any], fund_codes: set[str], fund_ids: set[str]) -> bool:
    if op.get("fund_code") in fund_codes:
        return True
    fund = op.get("fund")
    if isinstance(fund, dict):
        return fund.get("fund_code") in fund_codes or str(fund.get("id") or "") in fund_ids
    if fund is not None and str(fund) in fund_ids:
        return True
    return False


def prune_existing_operations(
    client: FundValClient,
    account_id: str,
    fund_codes: set[str],
    fund_ids: set[str],
    dry_run: bool,
) -> list[str]:
    deleted: list[str] = []
    for op in client.list_operations(account_id):
        if operation_matches_fund(op, fund_codes, fund_ids):
            deleted.append(op["id"])
            if not dry_run:
                client.delete_operation(op["id"])
    return deleted


def import_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    snapshot_path = Path(args.snapshot)
    snapshot = load_json(snapshot_path)
    snapshot_date, holdings = normalize_snapshot(snapshot)

    client = FundValClient(args.base_url, args.username, args.password)
    account_name = detect_account_name(snapshot, args.account)
    account_id = client.find_account_id(account_name)

    fund_codes = [str(item["fund_code"]).zfill(6) for item in holdings]
    if args.update_nav:
        client.update_navs(fund_codes)
    if args.update_estimate:
        client.update_estimates(fund_codes, args.estimate_source)

    synthetic_ops: list[dict[str, Any]] = []
    fund_ids: set[str] = set()
    for item in holdings:
        fund_code = str(item["fund_code"]).zfill(6)
        fund = client.get_fund(fund_code)
        if fund.get("id") is not None:
            fund_ids.add(str(fund["id"]))
        synthetic_ops.append(calculate_synthetic_buy(item, fund, snapshot_date))

    deleted_ids: list[str] = []
    if args.replace:
        deleted_ids = prune_existing_operations(client, account_id, set(fund_codes), fund_ids, args.dry_run)

    created: list[dict[str, Any]] = []
    for op in synthetic_ops:
        payload = {
            "account": account_id,
            "fund_code": op["fund_code"],
            "operation_type": op["operation_type"],
            "operation_date": op["operation_date"],
            "before_15": op["before_15"],
            "amount": op["amount"],
            "share": op["share"],
            "nav": op["nav"],
        }
        if args.dry_run:
            created.append({"dry_run": True, **payload})
        else:
            created.append(client.create_operation(payload))

    result = {
        "snapshot_file": str(snapshot_path),
        "snapshot_date": snapshot_date,
        "account_name": account_name,
        "account_id": account_id,
        "replace": args.replace,
        "dry_run": args.dry_run,
        "deleted_operation_ids": deleted_ids,
        "synthetic_operations": synthetic_ops,
        "created_operations": created,
        "raw_snapshot": snapshot,
    }

    if args.out:
        save_json(Path(args.out), result)

    return result


def parse_args() -> argparse.Namespace:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    default_password = os.environ.get("FUNDVAL_ADMIN_PASSWORD")
    parser = argparse.ArgumentParser(description="Import Alipay snapshot into FundVal-Live.")
    parser.add_argument("snapshot", help="Path to OCR-normalized Alipay snapshot JSON.")
    parser.add_argument("--base-url", default=os.environ.get("FUNDVAL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--username", default=os.environ.get("FUNDVAL_ADMIN_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password", default=default_password)
    parser.add_argument("--account", default=None, help=f"FundVal-Live child account name. Default: {DEFAULT_ACCOUNT_NAME}")
    parser.add_argument("--replace", action="store_true", help="Delete existing operations for the imported fund codes first.")
    parser.add_argument("--update-nav", action="store_true", help="Refresh latest NAV before calculating synthetic shares.")
    parser.add_argument("--update-estimate", action="store_true", help="Refresh intraday estimates after importing.")
    parser.add_argument("--estimate-source", default="yangjibao")
    parser.add_argument("--dry-run", action="store_true", help="Calculate operations but do not write them.")
    parser.add_argument("--out", default=None, help="Write an import report JSON.")
    args = parser.parse_args()
    if not args.password:
        parser.error("--password is required, or set FUNDVAL_ADMIN_PASSWORD in .env")
    return args


def main() -> None:
    result = import_snapshot(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
