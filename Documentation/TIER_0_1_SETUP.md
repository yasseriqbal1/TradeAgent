# Tier 0 & Tier 1 Implementation - Setup Guide

## 🎯 What Changed

### Tier 0 - Critical Before Live Trading (COMPLETED ✅)

1. **Dynamic Capital Detection** - Fetches live balance from Questrade API instead of hardcoded $100k
2. **Stock Affordability Filter** - Filters stocks by share price (max 30% of capital per share)
3. **10-Second Check Frequency** - Changed from 60 seconds to 10 seconds (6x faster)
4. **Position Sizing Adjustments** - Calculates shares based on actual account balance
5. **Pre-Flight Safety Checks** - Refuses to trade if balance < $150 or data > 24 hrs old

### Tier 1 - Critical for Safety (COMPLETED ✅)

1. **Position Persistence (PostgreSQL)** - Saves positions to database on every trade
2. **API Failure Discord Alerts** - Sends alerts on API timeouts/errors
3. **Position Reconciliation** - Compares DB vs broker positions on startup
4. **20% Drawdown Auto-Stop** - Automatically stops trading at -20% loss
5. **Graceful Remote Stop** - Create `logs/STOP_TRADING.txt` to stop trading remotely
6. **n8n Error Handling** - Workflow includes error notification nodes

---

## 📋 Setup Steps

### Step 1: Update Database Schema

The `positions` table already exists in your schema.sql, but you need to ensure it's created:

```bash
# Connect to PostgreSQL
psql -U postgres -d tradeagent

# Verify positions table exists
\d positions

# If it doesn't exist, create it:
```

```sql
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    quantity INT NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_date TIMESTAMP NOT NULL DEFAULT NOW(),
    current_price FLOAT NOT NULL,
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    max_hold_days INT NOT NULL,
    unrealized_pnl FLOAT DEFAULT 0,
    unrealized_pnl_pct FLOAT DEFAULT 0,
    position_value FLOAT,
    entry_order_id VARCHAR(50),
    stop_order_id VARCHAR(50),
    take_profit_order_id VARCHAR(50),
    signal_id VARCHAR(50),
    notes TEXT,
    exit_triggered BOOLEAN DEFAULT FALSE,
    exit_reason VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

### Step 2: Verify Database Credentials in .env

The database password is read from your `.env` file:

```bash
# Check your .env file contains:
DB_HOST=localhost
DB_NAME=tradeagent
DB_USER=postgres
DB_PASSWORD=your_actual_password_here
```

**All credentials are kept secure in .env file (not tracked in git)**

---

### Step 3: Test Database Connection

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run verification script (reads from .env automatically)
python verify_database_setup.py
```

### Step 4: Verify Questrade API Access

The script now calls these NEW API methods:

- `questrade.get_accounts()` - Get account list
- `questrade.get_balances(account_number)` - Get cash/equity
- `questrade.get_positions(account_number)` - Get current positions

**Test it:**

```bash
python -c "from quant_agent.questrade_loader import QuestradeAPI; q = QuestradeAPI(); accounts = q.get_accounts(); print(f'✅ Found {len(accounts)} accounts'); print(accounts[0])"
```

---

### Step 5: Run Data Download (REQUIRED Before Trading)

The script now refuses to trade if historical data is > 24 hours old:

```bash
# Download latest data
python download_historical_data.py

# Or use the wrapper script
.\run_download.ps1
```

---

### Step 6: Paper Test for 2 Days

**Starting with $200:**

1. **Day 1 Testing (Today)**

   ```bash
   # Run trading script manually
   python test_live_1hour_questrade.py
   ```

2. **What to Watch:**

   - ✅ Script fetches live balance ($200.00)
   - ✅ Only 4-5 affordable stocks shown (IONQ, QBTS, QUBT, RGTI)
   - ✅ Positions saved to database on BUY
   - ✅ Drawdown percentage displayed each check
   - ✅ Stops at -20% ($160 equity)

3. **Test Remote Stop:**

   ```bash
   # While script is running, create stop file
   echo "STOP" > logs\STOP_TRADING.txt
   ```

   - Script should close all positions and exit gracefully
   - Stop file should be auto-deleted

4. **Test Restart:**
   - Stop script (Ctrl+C)
   - Restart immediately
   - ✅ Positions should load from database
   - ✅ Position reconciliation should pass

---

## 🧪 Paper Testing Checklist

### Day 1 Tests

- [ ] Script fetches live balance from Questrade
- [ ] Affordable stocks filtered (should see 4-5 stocks only with $200)
- [ ] Position persistence works (check database after BUY)
- [ ] Restart loads positions from DB
- [ ] Position reconciliation passes on startup
- [ ] Remote stop file works (`logs/STOP_TRADING.txt`)
- [ ] Drawdown monitor displays correctly
- [ ] API error alerts sent to Discord (simulate by disconnecting WiFi briefly)

### Day 2 Tests

- [ ] 24-hour data freshness check works
- [ ] Drawdown auto-stop triggers at -20%
- [ ] Discord alerts work for critical errors
- [ ] n8n workflow executes without errors
- [ ] Positions update in DB every 10 seconds

---

## 🚀 Going Live After 2 Days

### Pre-Live Checklist

- [ ] Completed 2 full days of paper trading
- [ ] Database connection stable (no errors in logs)
- [ ] Position persistence working (restart test passed)
- [ ] Discord alerts received for test errors
- [ ] Ready to start with $200 real capital

### Live Trading Start

1. **Confirm Mode:**

   ```bash
   # Check .env file
   QUESTRADE_SERVER_TYPE=live  # NOT practice
   ```

2. **Start Trading:**

   ```bash
   # Run directly
   python test_live_1hour_questrade.py

   # Or via n8n (recommended)
   # n8n will start script at 9:30 AM automatically
   ```

3. **Monitor:**
   - Check Discord for trade alerts
   - Check logs/trades*log*\*.txt for details
   - Check database: `SELECT * FROM positions;`

---

## 🛠️ New Features Usage

### Remote Stop Trading

```bash
# From any terminal/script:
echo "STOP" > logs\STOP_TRADING.txt

# Script will:
# 1. Close all open positions
# 2. Log final state
# 3. Delete stop file
# 4. Exit gracefully
```

### Monitor Drawdown

Check log file for real-time drawdown:

```
📈 Current Status:
   Equity: $192.45
   P&L: -$7.55 (-3.78%)
   Cash: $150.23
   Positions: 2/3
   Drawdown: -3.78% (limit: -20%)
```

### Check Saved Positions

```sql
-- In PostgreSQL
SELECT ticker, quantity, entry_price, unrealized_pnl_pct, updated_at
FROM positions
WHERE exit_triggered = FALSE
ORDER BY updated_at DESC;
```

---

## ⚠️ Important Notes

### With $200 Starting Capital:

**Affordable Stocks (< $60/share):**

- IONQ (~$30)
- QBTS (~$5)
- QUBT (~$12)
- RGTI (~$8)

**Expensive Stocks (> $60/share) - FILTERED OUT:**

- NVDA ($140)
- GOOG ($314)
- TSLA ($240)
- AAPL ($230)
- Most others in your universe

**Position Sizing:**

- Max 3 positions = ~$66 per position
- Minus $1 commission = $65 usable
- Example: IONQ at $30/share → can buy 2 shares ($60 + $1 = $61 total cost)

**Commission Impact:**

- Each round-trip = $2 commission ($1 buy + $1 sell)
- On $66 position = 3% of capital
- Your 40% target becomes 37% net after commissions
- Your -15% stop becomes -18% net after commissions

**Drawdown Trigger:**

- Starting: $200
- Auto-stop at: $160 (-20%)
- Max loss tolerance: $40

---

## 📊 Success Metrics

### After 2 Days Paper Testing

- Zero database errors
- Zero reconciliation failures
- All positions persisted correctly
- Remote stop works 100%
- Drawdown monitor accurate

### After 1 Week Live ($200)

- No untracked positions
- No over-leverage
- Drawdown stayed above -20%
- All trades logged to DB
- Ready to increase to $500

---

## 🆘 Troubleshooting

### "Database connection failed"

```bash
# Check PostgreSQL is running
Get-Service -Name postgresql*

# Test connection
psql -U postgres -d tradeagent
```

### "No affordable stocks"

- Expected with $200 capital
- Only 4-5 stocks will be tradeable
- Increase capital to $500 for more options

### "Position reconciliation failed"

- **STOP TRADING IMMEDIATELY**
- Compare database vs Questrade manually
- Fix discrepancy before restarting

### "Stale data detected"

```bash
# Download fresh data
python download_historical_data.py
```

---

## ✅ Ready to Test

All code changes are complete. Follow steps above to:

1. Update database password
2. Test database connection
3. Download fresh data
4. Run 2-day paper test
5. Go live with $200

**Good luck! 🚀**
