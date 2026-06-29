#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from export_for_ai import DEFAULT_OUT as DEFAULT_AI_OUT, export_for_ai
from import_alipay_snapshot import import_snapshot, load_dotenv, load_json, save_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "history"
DEFAULT_IMPORT_REPORT = ROOT / "imports" / "last_import_report.json"


def snapshot_date_from_file(path: Path) -> str:
    data = load_json(path)
    value = data.get("snapshot_date")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return date.today().isoformat()


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_index_row(day: str, snapshot_path: Path, import_report: dict[str, Any], ai_export: dict[str, Any]) -> dict[str, Any]:
    summary = ai_export.get("summary") if isinstance(ai_export.get("summary"), dict) else {}
    return {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_file": str(snapshot_path),
        "position_count": summary.get("position_count"),
        "holding_cost": summary.get("holding_cost"),
        "holding_value": summary.get("holding_value"),
        "holding_profit": summary.get("holding_profit"),
        "estimate_value": summary.get("estimate_value"),
        "today_estimate_pnl": summary.get("today_estimate_pnl"),
        "fallback_count": summary.get("fallback_count"),
        "imported_count": len(import_report.get("synthetic_operations") or []),
    }


def copy_inputs(snapshot_path: Path, day_dir: Path, import_report_path: Path, ai_export_path: Path) -> None:
    day_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_path, day_dir / "alipay_snapshot.json")
    if import_report_path.exists():
        shutil.copy2(import_report_path, day_dir / "import_report.json")
    if ai_export_path.exists():
        shutil.copy2(ai_export_path, day_dir / "ai_portfolio_snapshot.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily Alipay snapshot import and archive AI-readable portfolio data.")
    parser.add_argument("snapshot", help="Path to the AI-normalized Alipay snapshot JSON.")
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--import-report", default=str(DEFAULT_IMPORT_REPORT))
    parser.add_argument("--ai-out", default=str(DEFAULT_AI_OUT))
    parser.add_argument("--dry-run", action="store_true", help="Do not write FundVal operations or history files.")
    parser.add_argument("--account", default=None)
    parser.add_argument("--base-url", default="http://localhost:21345")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    if not args.password:
        import os

        args.password = os.environ.get("FUNDVAL_ADMIN_PASSWORD")
    if not args.password:
        raise SystemExit("--password is required, or set FUNDVAL_ADMIN_PASSWORD in .env")

    snapshot_path = Path(args.snapshot)
    day = snapshot_date_from_file(snapshot_path)
    import_report_path = Path(args.import_report)
    ai_export_path = Path(args.ai_out)

    import_args = argparse.Namespace(
        snapshot=str(snapshot_path),
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        account=args.account,
        replace=True,
        update_nav=not args.dry_run,
        update_estimate=not args.dry_run,
        estimate_source="yangjibao",
        dry_run=args.dry_run,
        out=str(import_report_path),
    )
    import_report = import_snapshot(import_args)

    export_args = argparse.Namespace(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        out=str(ai_export_path),
    )
    ai_export = export_for_ai(export_args)

    result = {
        "date": day,
        "dry_run": args.dry_run,
        "import_report": str(import_report_path),
        "ai_export": str(ai_export_path),
        "summary": ai_export.get("summary"),
    }

    if not args.dry_run:
        history_dir = Path(args.history_dir)
        day_dir = history_dir / day
        copy_inputs(snapshot_path, day_dir, import_report_path, ai_export_path)
        append_jsonl(history_dir / "daily_index.jsonl", build_index_row(day, day_dir / "alipay_snapshot.json", import_report, ai_export))
        result["history_dir"] = str(day_dir)
        result["history_index"] = str(history_dir / "daily_index.jsonl")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
