# Trading Dashboard 📊

**Modern, clean, real-time dashboard for monitoring your trading bot.**

## ✨ Features

- **Real-time Updates**: Auto-refreshes every 15 seconds
- **Today's Summary**: P&L, Win Rate, Equity, Trade Count
- **Open Positions**: Live unrealized P&L with hold duration
- **Trade History**: Complete log of today's trades
- **Bot Status**: Live indicator showing if bot is active
- **Safety Features**: Display of all active protection systems
- **Dip Suggestions**: Lightweight dip/reversal ideas from live prices (hidden when market is closed or live data is missing)
- **Critical Monitoring**: Macro/context panel (VIX + WTI) plus external alerts pushed into Redis
- **Mobile Responsive**: Works on phone, tablet, desktop
- **Zero Interference**: Read-only mode, safe to run alongside bot

## 🚀 Quick Start

### Option 1: Double-click Startup File

```
dashboard/start_dashboard.bat    (Windows CMD)
OR
dashboard/start_dashboard.ps1    (Windows PowerShell)
```

### Option 2: Manual Start

```bash
cd dashboard
pip install -r requirements.txt
python app.py
```

Then open your browser to: **http://localhost:5000**

## 📋 What You'll See

### Top Metrics (Big Bold Numbers)

- **Net P&L**: Realized + Unrealized combined
- **Win Rate**: Percentage of winning trades
- **Current Equity**: Your account value
- **Trades Today**: Total buy/sell count

### Open Positions Table

| Column    | Description                         |
| --------- | ----------------------------------- |
| Ticker    | Stock symbol (styled badge)         |
| Shares    | Fractional shares owned             |
| Entry     | Your purchase price                 |
| Current   | Live market price                   |
| P&L       | Unrealized profit/loss ($ amount)   |
| %         | Unrealized profit/loss (percentage) |
| Hold Time | How long you've held position       |

### Trade History Table

- Chronological list of all today's trades
- BUY actions in green, SELL actions in red
- Winners in green, losers in red
- Shows exit reasons (Take Profit, Trailing Stop, etc.)

### Safety Features Panel

- Position Size Limit: 25% per trade ✅
- Trading Window: 9:35 AM - 3:55 PM EST ✅
- Earnings Blackout: ±30 minutes ✅
- Re-entry Cooldown: 15-20 minutes ✅

## 🎨 Design Style

**Modern Minimalist**

- Clean white background with subtle shadows
- Bootstrap 5 framework
- Smooth animations on updates
- Color-coded P&L (green = profit, red = loss)
- Professional yet easy to read

## 🔒 Safety

- **Read-only (DB)**: Only reads from database, never writes
- **No interference**: Bot doesn't know dashboard exists
- **Separate process**: Runs in its own terminal window
- **No broker trading**: Doesn't place orders
- **Limited market data calls**: Critical Monitoring fetches VIX/WTI via `yfinance` and caches results to reduce rate limits

## 🛠️ Technical Details

**Backend**: Python Flask
**Frontend**: HTML + Bootstrap 5 + Vanilla JavaScript
**Database**: PostgreSQL (read-only connection)
**Port**: 5000 (http://localhost:5000)
**Refresh Rate**: 15 seconds

**File Structure**:

```
dashboard/
├── app.py                    # Flask server (backend)
├── templates/
│   └── index.html           # Dashboard UI
├── static/
│   ├── css/
│   │   └── style.css        # Modern styling
│   └── js/
│       └── dashboard.js     # Auto-refresh logic
├── requirements.txt         # Python dependencies
├── start_dashboard.bat      # Windows CMD startup
├── start_dashboard.ps1      # PowerShell startup
└── README.md               # This file
```

## 📊 API Endpoints

The dashboard exposes these endpoints (for advanced users):

- `GET /` - Dashboard homepage
- `GET /api/summary` - Today's trading summary (JSON)
- `GET /api/positions` - Current open positions (JSON)
- `GET /api/trades` - Today's trade history (JSON)
- `GET /api/status` - Bot running status (JSON)
- `GET /api/dip-suggestions` - Dip suggestions (JSON). Returns `enabled:false` when market is closed or live Redis prices are missing/stale.
- `GET /api/critical-monitor` - Macro/context indicators + external alerts (JSON)

## ⚙️ Config (Env Vars)

Critical Monitoring:

- `VIX_WARN` / `VIX_CRITICAL` (defaults: `20` / `30`)
- `WTI_WARN` / `WTI_CRITICAL` (defaults: `65` / `80`)
- `CRITICAL_INDICATOR_CACHE_SECONDS` (default: `300`) – caches VIX/WTI to avoid rate limits
- `CRITICAL_FETCH_TIMEOUT_SECONDS` (default: `4`) – prevents the endpoint from hanging on slow quote responses

External alerts:

- Redis key: `critical_alerts_v1` (expects a JSON list of alert dicts)
- `CRITICAL_ALERTS_MAX` (default: `8`)

## 📰 Automatic News Alerts (Optional)

If you want the dashboard to surface market-moving headlines without you watching TV,
run the RSS monitor:

- Script: `dashboard/news_monitor.py`
- Starter: `dashboard/start_news_monitor.ps1`

It polls RSS/Atom feeds you configure, filters for keywords/tickers, and writes alerts into Redis.
Those alerts appear automatically under **Critical Monitoring**.

Minimal setup (in your project `.env`):

- `NEWS_RSS_URLS=https://www.sec.gov/rss/news/press.xml,https://www.federalreserve.gov/feeds/press_all.xml`
- `WATCHLIST_TICKERS=NVDA,MSFT,IONQ` (optional)

Tuning:

- `NEWS_POLL_SECONDS` (default `60`)
- `NEWS_MIN_SCORE` (default `3`) – higher = fewer alerts

## 🐛 Troubleshooting

**Dashboard won't start?**

- Make sure PostgreSQL is running
- Check `.env` file has correct database credentials
- Try: `pip install -r requirements.txt` manually

**No data showing?**

- Verify trading bot is running and has made trades today
- Check database connection in terminal output
- Refresh browser (F5)

**Port 5000 already in use?**

- Edit `app.py`, change `port=5000` to another port (e.g., 5001)

## 💡 Tips

1. **Keep it open**: Leave dashboard running all day to monitor trades
2. **Multiple screens**: Great for second monitor while trading
3. **Mobile**: Access from phone using `http://YOUR_PC_IP:5000`
4. **Bookmark it**: Save `http://localhost:5000` as browser bookmark

## 🎯 Next Steps

Want to customize?

- Edit `static/css/style.css` for colors/fonts
- Edit `templates/index.html` for layout changes
- Edit `static/js/dashboard.js` for refresh timing
- Edit `app.py` to add new data endpoints

## 📝 Notes

- Dashboard shows **today's data only** (resets at midnight)
- Auto-refresh keeps data current (no manual refresh needed)
- Bot status indicator shows green when active, yellow when idle
- All times displayed in Eastern Time (EST/EDT)

---

**Enjoy your professional trading dashboard!** 🚀

Questions? Check the code comments or review the Flask logs in terminal.
