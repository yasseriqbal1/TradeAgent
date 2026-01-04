# 🚀 Complete Setup Guide - Ready to Run

## 📊 Data Sources Overview

Your system uses **TWO different data sources**:

1. **Stooq (FREE)** - Historical data (5 years, daily OHLCV)

   - Used for: Momentum calculations, strategy backtesting
   - Downloads: Automatically via `download_all_stocks_stooq.py`
   - Frequency: Once daily at 8 AM (via n8n workflow)

2. **Questrade API (LIVE)** - Real-time quotes
   - Used for: Live trading decisions, current prices
   - Access: Via your API token in .env
   - Frequency: Every 10 seconds during trading (9:30 AM - 4 PM)

---

## ✅ Step-by-Step Setup

### Step 1: Download Historical Data (Stooq - ONE TIME)

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Download 5 years of historical data for 25 stocks from Stooq (FREE)
python download_all_stocks_stooq.py
```

**What it downloads:**

- 25 stocks (AAPL, AMD, CRWD, DDOG, GOOG, META, MSFT, MU, NET, NVDA, PLTR, SHOP, SNOW, IONQ, LAES, QBTS, QUBT, RGTI, AMZN, DIS, HD, NKE, SBUX, TSLA, WMT)
- ~5 years of daily data per stock
- Saves to: `historical_data/historical_data_TICKER.csv`

**Expected output:**

```
📊 AUTOMATED HISTORICAL DATA DOWNLOADER (STOOQ)
================================================================================
📂 Output Directory: historical_data
📋 Stocks to Download: 25
📅 Date Range: ~5 years of daily data
🌐 Source: Stooq.com (FREE)

[1/25] 📥 Downloading AAPL... ✅ 1256 days saved
[2/25] 📥 Downloading AMD... ✅ 1256 days saved
...
[25/25] 📥 Downloading WMT... ✅ 1256 days saved

📊 DOWNLOAD SUMMARY
================================================================================
✅ Successful: 25/25
❌ Failed: 0/25
```

⏱️ **Time:** 1-2 minutes

---

### Step 2: Verify Database Setup

```bash
# Test database connection (reads credentials from .env)
python verify_database_setup.py
```

**Expected output:**

```
✅ Successfully connected to PostgreSQL!
✅ Positions table exists!
✅ ALL CHECKS PASSED - Database ready for live trading!
```

---

### Step 3: Import n8n Workflow

**The correct workflow is:** `TradeAgent_Prod.json` (NOT production_workflow_READY.json)

1. Open n8n in browser: http://localhost:5678
2. Click **"Workflows"** → **"Import from File"**
3. Select: `n8n_workflows/TradeAgent_Prod.json`
4. Click **"Save"**

**What this workflow does:**

- **8:00 AM** - Downloads fresh data from Stooq
- **9:30 AM** - Starts live trading script
- **4:00 PM** - Reads trade log and sends daily summary to Discord
- **Real-time** - Forwards trade alerts (BUY/SELL) to Discord

---

### Step 4: Activate n8n Workflow

1. In n8n, open the imported workflow
2. Toggle the **"Active"** switch at top right
3. Workflow is now scheduled and ready

**Schedules set:**

- 8:00 AM - Data download (Mon-Fri)
- 9:30 AM - Trading starts (Mon-Fri)
- 4:00 PM - Market close summary (Mon-Fri)

---

### Step 5: Test Manual Run (Before Going Live)

**Test data download:**

```bash
.\run_download.ps1
```

**Expected:** Downloads complete in 1-2 minutes

**Test trading script (PAPER MODE):**

```bash
python test_live_1hour_questrade.py
```

**Watch for:**

- ✅ Fetches live balance from Questrade
- ✅ Shows 4-5 affordable stocks (with $200 capital)
- ✅ Saves positions to database
- ✅ Discord webhook alerts sent
- ✅ Checks every 10 seconds

**Stop with:** Ctrl+C or create `logs/STOP_TRADING.txt`

---

## 📋 Daily Workflow (Automated)

Once n8n workflow is active, this happens automatically every trading day:

```
7:00 AM - You wake up, check Discord
8:00 AM - n8n downloads fresh data from Stooq → Discord alert
9:30 AM - n8n starts trading script → Discord alert
9:30-4:00 PM - Script trades automatically (checks every 10 seconds)
             - Discord alerts on every BUY/SELL
4:00 PM - Market closes, script stops → Daily summary to Discord
```

**You don't need to do anything!** Just monitor Discord alerts.

---

## 🛠️ Manual Operations

### Download Data Manually

```bash
# Option 1: Via wrapper script (recommended)
.\run_download.ps1

# Option 2: Direct Python
python download_all_stocks_stooq.py
```

### Start Trading Manually

```bash
# Option 1: Via wrapper script (recommended)
.\run_trading.ps1

# Option 2: Direct Python
python test_live_1hour_questrade.py
```

### Remote Stop Trading

```bash
# Create stop file
echo "STOP" > logs\STOP_TRADING.txt

# Script will close all positions and exit gracefully
```

### Check Saved Positions

```sql
-- In PostgreSQL
psql -U postgres -d tradeagent

SELECT ticker, quantity, entry_price, unrealized_pnl_pct, updated_at
FROM positions
WHERE exit_triggered = FALSE;
```

### View Recent Logs

```bash
Get-Content logs\trades_log_*.txt -Tail 50
```

---

## 🔍 File Reference

### Configuration Files

- `.env` - API keys, database credentials (git-ignored)
- `requirements.txt` - Python dependencies

### Data Download

- `download_all_stocks_stooq.py` - Main download script (Stooq, FREE)
- `run_download.ps1` - Wrapper script for download
- `historical_data/` - Downloaded CSV files (25 stocks)

### Trading

- `test_live_1hour_questrade.py` - Main trading script
- `run_trading.ps1` - Wrapper script for trading
- `logs/` - Trade logs saved here

### Database

- `schema.sql` - Database schema (positions table)
- `verify_database_setup.py` - Connection tester

### n8n Workflow

- `n8n_workflows/TradeAgent_Prod.json` - ✅ USE THIS ONE
- `n8n_workflows/production_workflow_READY.json` - ❌ OLD, don't use

### API Client

- `quant_agent/questrade_loader.py` - Questrade API methods

---

## ⚙️ How Data Flows

```
┌─────────────────┐
│  Stooq (FREE)   │ ─── Daily at 8 AM ──→ historical_data/*.csv
└─────────────────┘                        (5 years history)
                                                  ↓
                                          [Momentum calculation]
                                                  ↓
┌─────────────────┐                       [Strategy logic]
│ Questrade API   │ ─── Every 10 sec ──→ [Current prices]
└─────────────────┘                              ↓
                                          [BUY/SELL decisions]
                                                  ↓
┌─────────────────┐                    ┌──────────────────┐
│  PostgreSQL DB  │ ←─── Save ────────│  Open positions  │
└─────────────────┘                    └──────────────────┘
                                                  ↓
┌─────────────────┐                       [Discord alerts]
│  Discord        │ ←─── Webhook ────────[Trade notifications]
└─────────────────┘
```

---

## 🚨 Important Notes

### 1. Historical Data Source

- **DO NOT use** `download_historical_data.py` (it uses yfinance)
- **ALWAYS use** `download_all_stocks_stooq.py` (FREE Stooq source)
- The wrapper `run_download.ps1` correctly calls Stooq script

### 2. Stock Universe

Both files now have the **same 25 stocks**:

- `download_all_stocks_stooq.py` - Downloads these 25
- `test_live_1hour_questrade.py` - Trades these 25

### 3. Data Freshness Check

The trading script will **refuse to trade** if historical data is > 24 hours old.

- Solution: Run `.\run_download.ps1` before trading

### 4. n8n Workflow

- `TradeAgent_Prod.json` - Updated with correct paths (logs/ folder)
- Has webhook for real-time trade alerts
- Auto-path detection in wrapper scripts

---

## ✅ Pre-Flight Checklist

Before going live, verify:

- [ ] Downloaded historical data (25 stocks from Stooq)
- [ ] Database connection works (`verify_database_setup.py`)
- [ ] `.env` has correct credentials (DB_PASSWORD, QUESTRADE_REFRESH_TOKEN)
- [ ] n8n workflow imported and activated
- [ ] Ran manual test and saw trades execute
- [ ] Discord webhook alerts received
- [ ] Positions saved to database
- [ ] Remote stop file works

---

## 🎯 Ready to Run!

**For 2-day paper testing:**

```bash
# Day 1: Test manually
python test_live_1hour_questrade.py

# Day 2: Let n8n run it automatically (activate workflow)
```

**After successful testing, go live with $200!**

All set! 🚀
