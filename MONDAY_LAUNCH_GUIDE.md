# 🚀 MONDAY LAUNCH GUIDE

## Quick Start

```bash
# 1. Activate environment
.\venv\Scripts\Activate.ps1

# 2. Start trading bot (after 9:35 AM)
python test_live_1hour_questrade.py
```

## ✅ New Safety Features Active

### Feature #1: Position Size Limit

- **Max per trade:** 20% of capital (accounts >$250)
- **Your account:** ~$96, so 25% allowed (flexibility)
- **Watch for:** "🚨 POSITION SIZE VIOLATION" in logs
- **Action:** None needed - auto-adjusts or blocks

### Feature #2: Trading Window

- **Active hours:** 9:35 AM - 3:55 PM EST only
- **Before 9:35 AM:** Bot will say "TRADING WINDOW BLOCKED"
- **After 3:55 PM:** Bot stops new entries
- **Action:** Don't start bot before 9:35 AM

### Feature #3: Earnings Blackout

- **Checks:** FMP API for earnings today
- **Blocks:** Stocks with earnings announcements
- **Watch for:** "🚫 {TICKER}: Earnings TODAY" in logs
- **Action:** None needed - blocks automatically

## 📊 What to Monitor

### In the logs, watch for:

```
✅ Position size check passed: $23.50 (24.5% of $96.00)
🚫 AAPL: Earnings TODAY at bmo (±30min blackout)
✅ MSFT: No earnings today
```

### Discord webhook will show:

- All safety violations (position size, earnings blocks)
- Time window enforcement
- Normal trade notifications

## 🔍 Expected Behavior

### First 5 minutes (9:30-9:35 AM):

```
🚫 TRADING WINDOW BLOCKED: Before 9:35 AM (avoiding open volatility)
```

→ **This is CORRECT. Wait until 9:35 AM.**

### Normal trading (9:35 AM - 3:55 PM):

```
✅ Within trading window
🔍 Scanning 55 stocks:
   ✅ Position size check passed...
   ✅ MU: No earnings today
   ✅ NVDA: No earnings today
```

→ **This is normal operation**

### If earnings detected:

```
🚫 NVDA: Earnings TODAY at amc - avoiding
```

→ **Stock is blocked. Bot moves to next stock.**

### Last 5 minutes (3:55-4:00 PM):

```
🚫 TRADING WINDOW BLOCKED: After 3:55 PM (avoiding close volatility)
```

→ **Correct. No new entries, but existing positions can exit.**

## ⚠️ Troubleshooting

### "API error 403" for earnings check

- **Normal on weekends**
- **On weekdays:** Check API key in .env file
- **Bot will:** Allow trades anyway (fail-open design)

### "Position size violation" on every trade

- **Check:** Is your capital calculation correct?
- **Look for:** "Account Size: $X" in logs
- **If <$250:** Should allow 25% per trade
- **If >$250:** Should cap at 20% per trade

### No trades happening

**Check these in order:**

1. Is time between 9:35 AM - 3:55 PM? ✅
2. Any stocks have earnings today? (blocks them)
3. Market regime OK? (VIX <35, SPY >200MA)
4. Consecutive losses <3?
5. Any stocks pass momentum filters?

## 📝 End of Day Review

### Questions to ask yourself:

1. How many trades were blocked by position size limit?
2. Did earnings blackout block any stocks?
3. Were there false positives (good trades blocked)?
4. Did I miss the first 5 minutes of open? (Good!)
5. Did bot stop new entries at 3:55 PM? (Good!)

### Stats to track:

- Total scans: \_\_\_
- Trades blocked by time window: \_\_\_
- Trades blocked by earnings: \_\_\_
- Trades blocked by position size: \_\_\_
- Actual trades executed: \_\_\_
- P&L: \_\_\_

## 🎯 Success Criteria for Monday

**Minimum requirements:**

- ✅ Bot blocks trades before 9:35 AM
- ✅ Bot blocks trades after 3:55 PM
- ✅ Position size validation runs on every entry
- ✅ Earnings API check happens (even if returns 403)
- ✅ At least 1 trade executed successfully in paper mode

**Bonus validation:**

- No crashes or exceptions
- All cooldown checks still working
- API token refresh happens at 25 min
- Discord webhooks include safety info

## 🚨 Emergency Commands

### Stop trading immediately:

```powershell
# Create stop file
New-Item -Path ".\logs\STOP_TRADING.txt" -ItemType File

# Or just Ctrl+C in terminal
```

### Check current status:

```powershell
# View last 20 log lines
Get-Content .\logs\trades_log_*.txt | Select-Object -Last 20
```

### Check for violations:

```powershell
# Search for safety blocks
Get-Content .\logs\trades_log_*.txt | Select-String "VIOLATION|BLOCKED|Earnings"
```

## 📞 When to Contact Me

**Immediate (stop trading):**

- Bot places order exceeding 20% when account >$250
- Bot trades during 9:30-9:35 AM or 3:55-4:00 PM
- Bot ignores earnings blackout and loses on gap

**Review after session:**

- Too many false positives (good trades blocked)
- API errors preventing normal operation
- Position size limits too restrictive

**NOT an issue:**

- Earnings API returns 403 on Sunday
- Bot blocks some stocks for earnings
- Bot adjusts position size down to safety limit
- Fewer trades than before (expected with safety features)

---

## 🎉 You're Ready!

All 3 critical safety features are live and tested.

**Remember:** These features exist to save your account when markets get crazy. They'll block some good trades, but they'll prevent catastrophic losses.

**Philosophy:** "Survive first, profit second."

Good luck on Monday! 🚀
