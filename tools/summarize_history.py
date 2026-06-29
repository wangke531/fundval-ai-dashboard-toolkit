#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from import_alipay_snapshot import save_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "history" / "daily_index.jsonl"
DEFAULT_OUT = ROOT / "exports" / "history_summary.json"


def D(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    rows.sort(key=lambda row: row.get("date") or "")
    return rows


def summarize(rows: list[dict[str, Any]], days: int | None) -> dict[str, Any]:
    if days and days > 0:
        rows = rows[-days:]
    if not rows:
        return {"count": 0, "rows": []}

    first = rows[0]
    last = rows[-1]
    first_value = D(first.get("holding_value"))
    last_value = D(last.get("holding_value"))
    first_profit = D(first.get("holding_profit"))
    last_profit = D(last.get("holding_profit"))
    today_values = [D(row.get("today_estimate_pnl")) for row in rows]
    today_values = [value for value in today_values if value is not None]

    best = max(rows, key=lambda row: D(row.get("today_estimate_pnl")) or Decimal("-999999999"))
    worst = min(rows, key=lambda row: D(row.get("today_estimate_pnl")) or Decimal("999999999"))

    return {
        "count": len(rows),
        "start_date": first.get("date"),
        "end_date": last.get("date"),
        "holding_value_start": first.get("holding_value"),
        "holding_value_end": last.get("holding_value"),
        "holding_value_change": money(last_value - first_value) if first_value is not None and last_value is not None else None,
        "holding_profit_start": first.get("holding_profit"),
        "holding_profit_end": last.get("holding_profit"),
        "holding_profit_change": money(last_profit - first_profit) if first_profit is not None and last_profit is not None else None,
        "today_estimate_pnl_sum": money(sum(today_values, Decimal("0"))) if today_values else None,
        "today_estimate_pnl_avg": money(sum(today_values, Decimal("0")) / Decimal(len(today_values))) if today_values else None,
        "best_day": {"date": best.get("date"), "today_estimate_pnl": best.get("today_estimate_pnl")},
        "worst_day": {"date": worst.get("date"), "today_estimate_pnl": worst.get("today_estimate_pnl")},
        "fallback_days": [row.get("date") for row in rows if D(row.get("fallback_count")) not in (None, Decimal("0"))],
        "rows": rows,
        "analysis_prompt": "Use this history to summarize weekly/monthly trend, drawdown days, data source quality, and position change notes. Do not provide deterministic financial advice.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize archived daily FundVal snapshots for AI analysis.")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--days", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = summarize(load_rows(Path(args.index)), args.days)
    save_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
