# Phase 3 Implementation Plan - Live Trading System

**Status:** Not Started  
**Estimated Time:** 3-4 weeks  
**Prerequisites:** Phase 1 ✅ Phase 2 ✅

---

## Overview

Phase 3 transforms the backtesting system into a live trading platform with real-time signal generation, order execution (paper trading first), position management, and monitoring.

---

## Module Breakdown

### Module 1: Real-Time Market Data Handler

**File:** `quant_agent/realtime_data.py` (~300 lines)

**Features:**

- WebSocket connection to Questrade streaming API
- Real-time quote updates (bid/ask/last)
- Level 2 order book data
- Market hours detection
- Connection management and reconnection logic
- Data validation and error handling

**Key Functions:**

```python
class RealtimeDataHandler:
    def connect_websocket()
    def subscribe_quotes(tickers: List[str])
    def get_latest_quote(ticker: str)
    def is_market_open()
    def handle_disconnection()
```

**Testing:**

- Connect to paper trading account
- Subscribe to 5-10 tickers
- Verify quote updates
- Test reconnection logic

---

### Module 2: Live Signal Generator

**File:** `quant_agent/live_signals.py` (~400 lines)

**Features:**

- Scheduled scanning (9:00 AM, 10:00 AM EST)
- Real-time factor calculation
- Signal generation using Phase 1 scorer
- Filter application (regime, correlation, earnings)
- Signal prioritization and ranking
- Signal persistence to database
- Change detection vs previous scan

**Key Functions:**

```python
class LiveSignalGenerator:
    def run_premarket_scan() -> List[Signal]
    def run_market_hours_scan() -> List[Signal]
    def calculate_realtime_factors(ticker: str)
    def apply_live_filters(signals: List[Signal])
    def compare_with_previous_scan()
    def save_signals_to_db()
```

**Scheduler:**

- 9:00 AM EST - Pre-market scan
- 10:00 AM EST - Market hours validation scan
- On-demand scan capability

**Testing:**

- Run scan at 9:00 AM
- Verify factors match historical
- Confirm filters working
- Check signal persistence

---

### Module 3: Order Management System

**File:** `quant_agent/order_manager.py` (~500 lines)

**Features:**

- Order creation and validation
- Paper trading mode (Phase 3A)
- Live trading mode (Phase 3B - future)
- Order types: Market, Limit, Stop Loss, Take Profit
- Order status tracking
- Fill confirmation handling
- Position synchronization
- Retry logic for failed orders

**Key Classes:**

```python
class OrderManager:
    def create_market_order(ticker, side, quantity)
    def create_limit_order(ticker, side, quantity, limit_price)
    def create_bracket_order(ticker, entry, stop_loss, take_profit)
    def submit_order(order: Order)
    def cancel_order(order_id: str)
    def get_order_status(order_id: str)
    def handle_fill(order_id: str)

class Order:
    id: str
    ticker: str
    side: str  # 'buy' or 'sell'
    quantity: int
    order_type: str
    status: str
    filled_price: float
    commission: float
```

**Testing:**

- Place paper trade orders
- Verify order submission
- Check fill handling
- Test cancellation

---

### Module 4: Position Manager

**File:** `quant_agent/position_manager.py` (~400 lines)

**Features:**

- Active position tracking
- P&L calculation (realized/unrealized)
- Position sizing enforcement
- Max positions limit
- Correlation checks before entry
- Automatic stop loss/take profit monitoring
- Exit signal detection
- Position close execution

**Key Functions:**

```python
class PositionManager:
    def get_active_positions() -> List[Position]
    def can_open_position(ticker: str) -> bool
    def open_position(signal: Signal, order: Order)
    def close_position(ticker: str, reason: str)
    def update_position_prices()
    def check_exit_conditions()
    def calculate_portfolio_pnl()
    def get_position_summary()
```

**Exit Conditions:**

- Stop loss hit
- Take profit hit
- Max hold days reached
- Signal reversal
- Manual close

**Testing:**

- Open test positions
- Track P&L updates
- Test exit triggers
- Verify position limits

---

### Module 5: Risk Monitor

**File:** `quant_agent/risk_monitor.py\*\* (~350 lines)

**Features:**

- Real-time portfolio risk assessment
- Position size validation
- Exposure limits (sector, correlation)
- Daily loss limits
- Margin/buying power checks
- Risk alerts and warnings
- Auto-stop on breach

**Risk Limits:**

```python
RISK_LIMITS = {
    'max_positions': 3,
    'max_position_pct': 40.0,          # % of portfolio
    'max_daily_loss_pct': 2.0,         # % drawdown limit
    'max_sector_exposure_pct': 60.0,   # % in one sector
    'max_correlation': 0.7,             # Position correlation
    'min_buying_power_pct': 20.0       # Reserve cash
}
```

**Key Functions:**

```python
class RiskMonitor:
    def check_pre_trade_risk(signal: Signal) -> bool
    def monitor_portfolio_risk()
    def calculate_var() # Value at Risk
    def check_daily_loss_limit()
    def send_risk_alert(message: str)
    def halt_trading() # Emergency stop
```

**Testing:**

- Test limit breaches
- Verify alerts
- Check position rejection
- Test halt mechanism

---

### Module 6: Trade Executor (Main Controller)

**File:** `quant_agent/trade_executor.py` (~600 lines)

**Features:**

- Main orchestrator for live trading
- Signal-to-order conversion
- Entry execution workflow
- Exit management
- Error handling and recovery
- State persistence
- Graceful shutdown

**Workflow:**

1. Receive signal from scanner
2. Run pre-trade checks (risk, filters)
3. Generate trade plan (size, stops, targets)
4. Submit entry order
5. Monitor for fill
6. Set stop loss and take profit
7. Track position
8. Execute exit on trigger
9. Record trade results

**Key Functions:**

```python
class TradeExecutor:
    def start() # Initialize system
    def process_signal(signal: Signal)
    def execute_entry(signal: Signal)
    def monitor_positions()
    def execute_exit(position: Position, reason: str)
    def handle_error(error: Exception)
    def shutdown() # Cleanup
```

**State Management:**

- Pending orders
- Active positions
- Exit triggers
- System status

**Testing:**

- Full signal-to-trade flow
- Error recovery
- System restart
- Emergency shutdown

---

### Module 7: Performance Tracker

**File:** `quant_agent/live_performance.py` (~300 lines)

**Features:**

- Daily P&L tracking
- Trade statistics (real-time)
- Win rate monitoring
- Sharpe ratio calculation
- Drawdown tracking
- Equity curve generation
- Comparison vs benchmarks (SPY)

**Key Metrics:**

- Today's P&L
- Week's P&L
- Month's P&L
- Total return
- Win rate (today/week/month/all-time)
- Sharpe ratio
- Max drawdown
- Active positions value
- Cash balance

**Key Functions:**

```python
class LivePerformanceTracker:
    def update_daily_pnl()
    def record_closed_trade(trade: Trade)
    def calculate_metrics() -> Dict
    def get_equity_curve() -> pd.DataFrame
    def generate_daily_report()
    def compare_to_benchmark()
```

**Testing:**

- Track test trades
- Verify calculations
- Check daily rollover
- Test report generation

---

### Module 8: Alert & Notification System

**File:** `quant_agent/alerts.py` (~250 lines)

**Features:**

- Email notifications
- SMS alerts (via Twilio)
- Discord/Slack webhooks
- Alert levels (INFO, WARNING, CRITICAL)
- Configurable alert rules
- Rate limiting

**Alert Types:**

1. **Trading Alerts:**

   - New signal generated
   - Position opened
   - Position closed
   - Stop loss hit
   - Take profit hit

2. **Risk Alerts:**

   - Daily loss limit approaching
   - Position size exceeded
   - Correlation breach
   - Buying power low

3. **System Alerts:**
   - Connection lost
   - API error
   - Data feed issue
   - System startup/shutdown

**Key Functions:**

```python
class AlertManager:
    def send_email(subject: str, body: str)
    def send_sms(message: str)
    def send_webhook(webhook_url: str, message: str)
    def alert(level: str, message: str)
```

**Configuration:**

```python
ALERT_CONFIG = {
    'email_enabled': True,
    'email_to': 'your@email.com',
    'sms_enabled': False,
    'discord_webhook': 'https://...',
    'alert_on_entry': True,
    'alert_on_exit': True,
    'alert_on_risk_breach': True
}
```

**Testing:**

- Send test alerts
- Verify delivery
- Check rate limiting
- Test all channels

---

### Module 9: Trading Dashboard (Optional/Enhanced)

**File:** `dashboard/app.py` (~800 lines)

**Features:**

- Web-based dashboard (Streamlit or Dash)
- Live portfolio view
- Active positions table
- Recent trades log
- Performance charts
- Signal queue display
- Manual controls (pause/resume)
- System status

**Pages:**

1. **Overview** - Portfolio summary, today's P&L, positions
2. **Signals** - Current signals, signal history
3. **Positions** - Active positions with live P&L
4. **Trades** - Trade history with filters
5. **Performance** - Charts and metrics
6. **Settings** - Configuration and controls

**Key Features:**

```python
# Streamlit example
def show_portfolio_overview()
def show_active_positions()
def show_recent_signals()
def show_performance_charts()
def show_system_controls()
```

**Testing:**

- Launch dashboard
- Verify real-time updates
- Test controls
- Check all pages

---

## Implementation Phases

### Phase 3A: Paper Trading (Weeks 1-2)

**Goal:** Fully functional paper trading system

**Tasks:**

1. Implement real-time data handler
2. Build live signal generator
3. Create paper trading order manager
4. Implement position manager
5. Add risk monitor
6. Build trade executor
7. Add basic alerts
8. Testing and debugging

**Deliverable:** System that generates signals and executes paper trades automatically

---

### Phase 3B: Live Trading Preparation (Weeks 3-4)

**Goal:** Production-ready live trading system

**Tasks:**

1. Switch order manager to live mode
2. Implement performance tracker
3. Build comprehensive alert system
4. Create trading dashboard
5. Add logging and monitoring
6. Write operation manual
7. Stress testing
8. Small-scale live testing ($1k-$5k)

**Deliverable:** Production system ready for live capital

---

## Database Schema Updates

### New Tables

**live_signals**

```sql
CREATE TABLE live_signals (
    id SERIAL PRIMARY KEY,
    scan_run_id INT REFERENCES scan_runs(id),
    ticker VARCHAR(10),
    signal_date TIMESTAMP,
    composite_score FLOAT,
    price FLOAT,
    factors JSONB,
    trade_plan JSONB,
    selected BOOLEAN DEFAULT false,
    executed BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**orders**

```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE,
    ticker VARCHAR(10),
    side VARCHAR(10),
    quantity INT,
    order_type VARCHAR(20),
    status VARCHAR(20),
    submitted_price FLOAT,
    filled_price FLOAT,
    commission FLOAT,
    submitted_at TIMESTAMP,
    filled_at TIMESTAMP,
    signal_id INT REFERENCES live_signals(id)
);
```

**positions**

```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10),
    quantity INT,
    entry_price FLOAT,
    entry_date TIMESTAMP,
    stop_loss FLOAT,
    take_profit FLOAT,
    current_price FLOAT,
    unrealized_pnl FLOAT,
    status VARCHAR(20),
    entry_order_id INT REFERENCES orders(id)
);
```

**live_trades**

```sql
CREATE TABLE live_trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10),
    entry_date TIMESTAMP,
    entry_price FLOAT,
    exit_date TIMESTAMP,
    exit_price FLOAT,
    quantity INT,
    pnl FLOAT,
    pnl_pct FLOAT,
    hold_days INT,
    exit_reason VARCHAR(50),
    commission FLOAT,
    signal_id INT REFERENCES live_signals(id),
    position_id INT REFERENCES positions(id)
);
```

**risk_events**

```sql
CREATE TABLE risk_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Configuration File

**config/live_trading.yaml**

```yaml
trading:
  mode: "paper" # or 'live'
  initial_capital: 100000
  max_positions: 3
  max_position_pct: 40.0
  commission_per_trade: 1.0
  slippage_pct: 0.05

risk:
  max_daily_loss_pct: 2.0
  max_sector_exposure_pct: 60.0
  max_correlation: 0.7
  min_buying_power_pct: 20.0
  halt_on_loss_limit: true

schedule:
  premarket_scan: "09:00"
  market_scan: "10:00"
  timezone: "America/New_York"

filters:
  enable_regime_filter: true
  enable_correlation_filter: true
  enable_earnings_filter: true
  min_score_threshold: 60.0

alerts:
  email_enabled: true
  email_to: "your@email.com"
  discord_webhook: null
  alert_on_entry: true
  alert_on_exit: true
  alert_on_risk_breach: true
```

---

## Testing Plan

### Unit Tests

- Each module tested independently
- Mock data for order execution
- Risk limit validation
- Alert delivery

### Integration Tests

- Full signal-to-trade workflow
- Position lifecycle (open → monitor → close)
- Risk monitor integration
- Database persistence

### Paper Trading Tests (1-2 weeks)

- Run system with paper account
- Monitor for bugs
- Verify execution logic
- Track performance

### Stress Tests

- Handle rapid market moves
- Connection loss scenarios
- API errors
- High volatility conditions

---

## Risk Management Checklist

Before going live:

- [ ] Paper trading successful for 2+ weeks
- [ ] All risk limits tested and working
- [ ] Emergency stop mechanism verified
- [ ] Position sizing validated
- [ ] Stop losses executing correctly
- [ ] Data feed reliability confirmed
- [ ] Alert system functioning
- [ ] Backup procedures in place
- [ ] Small capital test ($1k-$5k)
- [ ] Written operation manual

---

## Success Metrics

### Phase 3A (Paper Trading)

- [ ] System runs autonomously for 2 weeks
- [ ] Generates and executes 20+ signals
- [ ] No critical bugs or crashes
- [ ] Risk limits respected
- [ ] Position management working
- [ ] Performance tracking accurate

### Phase 3B (Live Trading)

- [ ] First week live with no issues
- [ ] Positive or breakeven performance
- [ ] All alerts firing correctly
- [ ] Dashboard showing accurate data
- [ ] Risk events logged properly
- [ ] Ready to scale capital

---

## Timeline Summary

**Week 1:** Real-time data + Signal generator + Order manager basics  
**Week 2:** Position manager + Risk monitor + Trade executor + Paper testing  
**Week 3:** Performance tracker + Alert system + Dashboard + Live prep  
**Week 4:** Testing + Documentation + Small live deployment

**Total:** 4 weeks to production-ready live trading system

---

## Dependencies & Requirements

### Python Packages

```
streamlit>=1.28.0        # Dashboard
twilio>=8.10.0          # SMS alerts
discord-webhook>=1.3.0   # Discord notifications
schedule>=1.2.0         # Task scheduling
websockets>=12.0        # Real-time data
python-dotenv>=1.0.0    # Environment config
pyyaml>=6.0            # Config files
```

### External Services

- Questrade account (paper + live)
- Email SMTP server
- SMS service (optional)
- Discord/Slack webhook (optional)

### Infrastructure

- Always-on server or VPS (for live trading)
- PostgreSQL database
- Backup system
- Monitoring (uptime checks)

---

## Next Steps

1. **Review this plan** - Confirm scope and priorities
2. **Set up paper trading account** - Get credentials
3. **Start Module 1** - Real-time data handler
4. **Iterate through modules** - Build incrementally
5. **Test thoroughly** - Paper trade 2 weeks minimum
6. **Deploy to production** - Start with small capital

---

## Notes

- Phase 3A focuses on paper trading to validate logic safely
- Phase 3B adds production features and live execution
- Dashboard is optional but highly recommended
- Start with conservative position sizing
- Monitor closely for first 2-4 weeks of live trading
- Scale capital gradually as confidence builds

**Estimated Total Time:** 3-4 weeks full-time, 6-8 weeks part-time
