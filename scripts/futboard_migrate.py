#!/usr/bin/env python3
"""Create the FUTBOARD schema on Neon.

    export $(grep FUTBOARD_DATABASE_URL backend/.env | xargs)
    python scripts/futboard_migrate.py            # create what is missing
    python scripts/futboard_migrate.py --check    # report only, change nothing

The DDL is entirely `CREATE ... IF NOT EXISTS`, so running it twice is a no-op.
It is deliberately *not* run at application startup: the backend runs on a
single replica with 0.25 vCPU, and a schema change is something to do knowingly
rather than as a side effect of a deploy that happened to restart the container.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
for _path in (ROOT_DIR, ROOT_DIR / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

EXPECTED_TABLES = {"teams", "players", "team_players", "matches", "match_players", "goals"}


def _database_url() -> str:
    url = os.environ.get("FUTBOARD_DATABASE_URL")
    if not url:
        # Fall back to the same .env the backend reads, so the script works from
        # a checkout without exporting anything by hand.
        env_file = ROOT_DIR / "backend" / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("FUTBOARD_DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    if not url:
        raise SystemExit(
            "error: FUTBOARD_DATABASE_URL is not set and backend/.env does not define it."
        )
    return url


def existing_tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    ).fetchall()
    return {row[0] for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report only, write nothing")
    args = parser.parse_args()

    import psycopg

    from app.services.futboard_store import SCHEMA

    url = _database_url()
    host = url.split("@", 1)[-1].split("/", 1)[0]
    print(f"host: {host}")

    with psycopg.connect(url, connect_timeout=25) as conn:
        before = existing_tables(conn)
        missing = EXPECTED_TABLES - before
        print(f"present: {sorted(before & EXPECTED_TABLES) or '(none)'}")
        print(f"missing: {sorted(missing) or '(none)'}")

        if args.check:
            return 0 if not missing else 1

        conn.execute(SCHEMA)
        conn.commit()
        after = existing_tables(conn)

    created = sorted(after - before)
    print(f"created: {created or '(nothing, already up to date)'}")

    still_missing = EXPECTED_TABLES - after
    if still_missing:
        print(f"ERROR: still missing after migration: {sorted(still_missing)}")
        return 1
    print("schema ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
