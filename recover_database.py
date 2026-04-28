"""Recover TradeAgent PostgreSQL schema after table loss/corruption.

Usage:
    .venv\\Scripts\\python.exe recover_database.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


REQUIRED_TABLES = [
    "scan_runs",
    "signals",
    "factors",
    "trades_history",
    "live_signals",
    "orders",
    "positions",
    "live_trades",
    "risk_events",
]


def get_db_params() -> dict:
    load_dotenv()
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "tradeagent"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def read_migration_file() -> str:
    migration_path = Path(__file__).parent / "migrations" / "003_recover_corrupted_database.sql"
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_path}")
    return migration_path.read_text(encoding="utf-8")


def run_recovery() -> int:
    params = get_db_params()
    sql = read_migration_file()

    conn = None
    try:
        conn = psycopg2.connect(**params)
        conn.autocommit = False

        with conn.cursor() as cur:
            cur.execute(sql)

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                ORDER BY table_name
                """,
                (REQUIRED_TABLES,),
            )
            existing_tables = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT COUNT(*) FROM positions")
            positions_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM trades_history")
            trades_history_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM scan_runs")
            scan_runs_count = cur.fetchone()[0]

        conn.commit()

        missing = sorted(set(REQUIRED_TABLES) - set(existing_tables))
        print("Recovery migration applied successfully.")
        print(f"Tables present ({len(existing_tables)}/{len(REQUIRED_TABLES)}): {', '.join(existing_tables)}")
        print(f"Row counts: positions={positions_count}, trades_history={trades_history_count}, scan_runs={scan_runs_count}")

        if missing:
            print(f"Missing required tables: {', '.join(missing)}")
            return 2

        return 0
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        print(f"Database recovery failed: {exc}")
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(run_recovery())