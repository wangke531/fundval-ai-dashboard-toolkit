#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: tools/daily_update.sh path/to/alipay_snapshot.json [--dry-run]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT="$1"
shift

cd "$ROOT"
python3 ./tools/daily_update.py "$SNAPSHOT" "$@"
