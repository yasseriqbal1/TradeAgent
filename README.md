# TradeAgent - Multi-Factor Stock Scanner

AI-powered stock screening system with dual daily scans (9am & 10am EST).

## Features

- Technical factor analysis (momentum, volatility, volume)
- Pre-market scan (9am EST) - Previous day's data
- Validation scan (10am EST) - Fresh market data
- PostgreSQL persistence
- FastAPI service
- n8n automation with Groq AI summaries

## Quick Start

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start FastAPI service
uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000 --reload
```

## Architecture

- **Python/FastAPI**: Quant engine
- **PostgreSQL**: Data storage
- **yfinance**: Market data
- **pandas-ta**: Technical indicators
- **n8n**: Scheduling & notifications
- **Groq AI**: Report generation

## Endpoints

- `GET /health` - Health check
- `GET /scan/premarket` - 9am scan (top 10 stocks)
- `GET /scan/validation` - 10am validation scan

## Configuration

Edit `.env` for database, API keys, and emails.

---

## 🚀 Complete Setup

### Phase 1: Python Backend ✅ COMPLETE

- Database schema created
- FastAPI service running
- Technical factors implemented
- yfinance data loader ready

### Phase 2: n8n Automation ✅ COMPLETE

See **[QUICKSTART.md](QUICKSTART.md)** for complete setup instructions.

**Quick Steps:**

1. Start FastAPI: `python -m uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000`
2. Start n8n: `npx n8n`
3. Import workflows from `n8n_workflows/`
4. Configure email credentials
5. Activate workflows

**Documentation:**

- [QUICKSTART.md](QUICKSTART.md) - Complete setup guide
- [n8n_workflows/n8n_setup_guide.md](n8n_workflows/n8n_setup_guide.md) - Detailed n8n config
- [n8n_workflows/email_setup.md](n8n_workflows/email_setup.md) - Email provider setup
- [n8n_workflows/groq_prompts.md](n8n_workflows/groq_prompts.md) - AI prompt engineering

---

## 📊 What It Does

**9:00 AM EST - Pre-Market Scan:**

- Scans S&P 100 stocks
- Calculates momentum, volatility, volume factors
- Ranks by composite score
- Groq AI generates analysis
- Emails top 10 picks with detailed breakdown

**10:00 AM EST - Validation Scan:**

- Re-scans top 10 with fresh data
- Detects changes (drops, adds, price moves)
- Groq AI analyzes changes
- Emails alert ONLY if significant changes

---

## 🎯 Current Status

**Backend:**

- ✅ PostgreSQL database
- ✅ FastAPI service (8 endpoints)
- ✅ yfinance data loader with caching
- ✅ 10+ technical indicators (RSI, EMA, ATR, volatility, volume)
- ✅ Z-score normalization
- ✅ Composite scoring algorithm
- ✅ Pre-market & validation scan logic

**Automation:**

- ✅ n8n workflow files created
- ✅ Groq AI integration configured
- ✅ Email templates (HTML formatted)
- ✅ Cron scheduling (9am, 10am EST)

**Ready to use!** Just follow [QUICKSTART.md](QUICKSTART.md)

---

## 📁 Project Structure

```
TradeAgent/
├── quant_agent/              # Python package
│   ├── config.py            # Settings, universe, factor weights
│   ├── database.py          # PostgreSQL operations
│   ├── data_loader.py       # yfinance wrapper
│   ├── factors.py           # Technical indicators
│   ├── scoring.py           # Composite scoring
│   ├── scanner.py           # Main scan logic
│   └── service.py           # FastAPI endpoints
├── n8n_workflows/           # n8n automation
│   ├── premarket_scan_workflow.json
│   ├── validation_scan_workflow.json
│   ├── n8n_setup_guide.md
│   ├── email_setup.md
│   └── groq_prompts.md
├── data/                    # Price data cache
├── logs/                    # Application logs
├── .env                     # Configuration
├── requirements.txt         # Dependencies
├── QUICKSTART.md           # Setup guide
└── start_services.ps1      # Launch script
```

---

## ⚙️ Configuration

**Edit [config.py](quant_agent/config.py) to customize:**

- Stock universe (default: S&P 100)
- Factor weights (momentum: 40%, volume: 30%, volatility: 30%)
- Filters (min price $5, min volume 500K)
- Technical indicator periods

**Edit [.env](.env) for:**

- PostgreSQL credentials
- Groq API key
- Email recipients

---

## 🔧 Maintenance

**View scan history:**

```bash
curl http://127.0.0.1:8000/scan/history
```

**Check latest signals:**

```bash
curl http://127.0.0.1:8000/signals/latest
```

**Monitor logs:**

- FastAPI: Terminal output
- n8n: Executions tab in UI
- Database: `SELECT * FROM scan_runs ORDER BY run_timestamp DESC LIMIT 10;`

---

## 📈 Future Enhancements (Phase 3)

- [ ] Fundamental factors (P/E, ROE) when using paid data
- [ ] ML model training (scikit-learn)
- [ ] Backtesting module (vectorbt)
- [ ] Risk parity portfolio weighting
- [ ] Sector rotation detection
- [ ] Multi-timeframe analysis
- [ ] Live paper trading integration
- [ ] Performance tracking dashboard

---

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Not financial advice.
Technical signals have a 5-20 day horizon and require active risk management.
Past performance does not guarantee future results. Consult a licensed financial
advisor before making investment decisions.
