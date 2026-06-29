#!/usr/bin/env python3
from __future__ import annotations

import json
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / "config" / "config.example.json"
OUT_PATH = ROOT / "config" / "config.runtime.json"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    if not ENV_PATH.exists():
        raise SystemExit("Missing .env. Copy .env.example to .env first.")

    env = load_env(ENV_PATH)
    config = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    db = config["db_config"]

    db["host"] = env.get("POSTGRES_HOST") or env.get("DB_HOST") or db["host"]
    db["port"] = int(env.get("POSTGRES_PORT") or env.get("DB_PORT") or db["port"])
    db["name"] = env.get("POSTGRES_DB") or db["name"]
    db["user"] = env.get("POSTGRES_USER") or db["user"]
    db["password"] = env.get("POSTGRES_PASSWORD") or db["password"]
    config["bootstrap_key"] = env.get("FUNDVAL_BOOTSTRAP_KEY") or secrets.token_urlsafe(48)

    OUT_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
