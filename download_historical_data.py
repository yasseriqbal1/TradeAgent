"""Bulk historical data downloader.

This script refreshes the CSVs used by the trading bot's momentum engine.

The bot expects files at:
  historical_data/historical_data_{TICKER}.csv

with a Date index column (so it can load via `index_col='Date', parse_dates=True`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import argparse
import re

import pandas as pd
import yfinance as yf


def project_root() -> Path:
    return Path(__file__).resolve().parent


def detect_tickers_from_historical_data_dir(data_dir: Path) -> list[str]:
    tickers: list[str] = []
    pattern = re.compile(r"^historical_data_(?P<ticker>[A-Z0-9._-]+)\.csv$")
    if not data_dir.exists():
        return tickers

    for path in sorted(data_dir.glob("historical_data_*.csv")):
        match = pattern.match(path.name)
        if match:
            tickers.append(match.group("ticker"))
    return tickers


def _read_existing_last_date(csv_path: Path) -> pd.Timestamp | None:
    try:
        df = pd.read_csv(csv_path, parse_dates=['Date'])
        if df.empty:
            return None
        return pd.to_datetime(df['Date']).max()
    except Exception:
        return None


def refresh_existing_csvs(
    tickers: list[str],
    output_dir: Path,
    years: int = 2,
    force_full: bool = False,
):
    """Fast refresh: bulk-download missing tail data with yfinance and append to CSVs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().date()
    end_exclusive = today + timedelta(days=1)  # yfinance end is exclusive

    csv_paths = {t: (output_dir / f"historical_data_{t}.csv") for t in tickers}
    last_dates: dict[str, pd.Timestamp | None] = {t: _read_existing_last_date(p) for t, p in csv_paths.items()}

    if force_full:
        start_date = today - timedelta(days=years * 365)
    else:
        # Incremental start: (min last_date among existing) or years fallback
        existing_dates = [d for d in last_dates.values() if d is not None]
        if existing_dates:
            start_date = (min(existing_dates).date() - timedelta(days=3))
        else:
            start_date = today - timedelta(days=years * 365)

    print(f"\nFast refresh window: {start_date} -> {end_exclusive} (end exclusive)")

    # Bulk download
    data = yf.download(
        tickers=tickers,
        start=start_date.strftime('%Y-%m-%d'),
        end=end_exclusive.strftime('%Y-%m-%d'),
        group_by='ticker',
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    updated = 0
    failed: list[str] = []

    for ticker in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.get_level_values(0):
                    failed.append(ticker)
                    continue
                df_new = data[ticker].copy()
            else:
                # Single ticker download returns a flat frame
                df_new = data.copy()

            if df_new is None or df_new.empty:
                failed.append(ticker)
                continue

            # Normalize columns and index
            df_new = df_new.rename(columns={'Adj Close': 'AdjClose'})
            keep_cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df_new.columns]
            df_new = df_new[keep_cols]
            df_new.index = pd.to_datetime(df_new.index)
            df_new.index.name = 'Date'
            df_new = df_new.dropna(subset=['Close'])

            out_path = csv_paths[ticker]
            if out_path.exists() and not force_full:
                df_old = pd.read_csv(out_path, parse_dates=['Date']).set_index('Date')
                df_old.index = pd.to_datetime(df_old.index)
                df_old = df_old[[c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df_old.columns]]
                df_combined = pd.concat([df_old, df_new], axis=0)
                df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
                df_combined = df_combined.sort_index()
            else:
                df_combined = df_new.sort_index()

            df_combined.to_csv(out_path)
            updated += 1
        except Exception:
            failed.append(ticker)

    print(f"\n✅ Updated: {updated}/{len(tickers)}")
    if failed:
        print(f"❌ Failed: {', '.join(failed[:12])}{'...' if len(failed) > 12 else ''}")

    return updated, failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh bot historical_data CSVs using yfinance")
    parser.add_argument(
        "--tickers",
        nargs="*",
        help="Tickers to download. If omitted, auto-detect from historical_data/historical_data_*.csv",
    )
    parser.add_argument("--years", type=int, default=2, help="Years of history to download (default: 2)")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full re-download (slower). Default is fast incremental refresh.",
    )
    args = parser.parse_args()

    root = project_root()
    data_dir = root / "historical_data"

    tickers = [t.strip().upper() for t in (args.tickers or []) if t.strip()]
    if not tickers:
        tickers = detect_tickers_from_historical_data_dir(data_dir)

    if not tickers:
        raise SystemExit(
            "No tickers provided and none detected. Provide --tickers, or create files in historical_data/ first."
        )

    print("=" * 70)
    print("Refreshing bot historical data")
    print("=" * 70)

    # Fast path by default for "market is about to open" scenarios.
    refresh_existing_csvs(tickers, output_dir=data_dir, years=args.years, force_full=args.full)

    print("\nDone. Next: re-run the bot; the freshness check should pass.")
