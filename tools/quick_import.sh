#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: tools/quick_import.sh path/to/alipay_snapshot.json [--dry-run] [--out path] [--account name]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT="$1"
shift

OUT="./imports/last_import_report.json"
ACCOUNT=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --out)
      OUT="$2"
      shift 2
      ;;
    --account)
      ACCOUNT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$ROOT"

ARGS=(
  "./tools/import_alipay_snapshot.py"
  "$SNAPSHOT"
  "--replace"
  "--out"
  "$OUT"
)

if [[ -n "$ACCOUNT" ]]; then
  ARGS+=("--account" "$ACCOUNT")
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  ARGS+=("--dry-run")
else
  ARGS+=("--update-nav" "--update-estimate" "--estimate-source" "yangjibao")
fi

python3 "${ARGS[@]}"
