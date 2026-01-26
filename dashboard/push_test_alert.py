"""One-off helper: push a single test alert into Redis for the dashboard.

Usage (PowerShell):
  cd dashboard
  "C:/Users/training/Documents/Python Projects/TradeAgent/.venv/Scripts/python.exe" push_test_alert.py

This does not impact the trading bot.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv

try:
    import redis  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(f"redis package not available: {e}")


def main() -> int:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

    r = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )
    r.ping()

    key = "critical_alerts_v1"
    raw = r.get(key)
    alerts = []
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                alerts = parsed
        except Exception:
            alerts = []

    alerts.append(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "severity": "warning",
            "title": "TEST (click): Market-moving headline example",
            "message": "Injected test alert so you can see the clickable title.",
            "source": "manual-test",
            "url": "https://www.sec.gov/news/pressreleases",
            "matched": ["NVDA", "IONQ"],
        }
    )

    r.set(key, json.dumps(alerts))
    print(f"Inserted 1 alert into {key}. total={len(alerts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
