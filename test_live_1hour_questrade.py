"""
Live Paper Trading using Questrade
Runs continuously during market hours with real-time data
Creates detailed trade log in trades_log_TIMESTAMP.txt
Press Ctrl+C to stop
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import time as time_sleep
import os
import random
from glob import glob
from pathlib import Path
import requests
from dotenv import load_dotenv
import json
import redis

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


def get_now_eastern():
    """Return current time in US/Eastern (handles DST when available)."""
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("America/New_York"))


def get_us_market_state(now=None):
    """Return (is_open, reason, next_open_dt) for US equities regular session."""
    if now is None:
        now = get_now_eastern()
    elif ZoneInfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("America/New_York"))

    session_open = time(9, 30)
    session_close = time(16, 0)

    # Weekend
    if now.weekday() >= 5:
        reason = "Weekend"
    else:
        # Holiday (best-effort)
        is_holiday = False
        try:
            from pandas.tseries.holiday import USFederalHolidayCalendar

            cal = USFederalHolidayCalendar()
            is_holiday = len(cal.holidays(start=now.date(), end=now.date())) > 0
        except Exception:
            is_holiday = False

        if is_holiday:
            reason = "US market holiday"
        elif now.time() < session_open:
            reason = "Pre-market (before 9:30 AM ET)"
        elif now.time() >= session_close:
            reason = "After-hours (after 4:00 PM ET)"
        else:
            return True, "Market open", None

    # Compute next open (ET)
    next_day = now.date()
    if now.time() < session_open and now.weekday() < 5:
        candidate_ok = True
        try:
            from pandas.tseries.holiday import USFederalHolidayCalendar

            cal = USFederalHolidayCalendar()
            candidate_ok = len(cal.holidays(start=next_day, end=next_day)) == 0
        except Exception:
            candidate_ok = True

        if candidate_ok:
            if ZoneInfo is None:
                next_open = datetime.combine(next_day, session_open)
            else:
                next_open = datetime.combine(next_day, session_open, tzinfo=ZoneInfo("America/New_York"))
            return False, reason, next_open

    while True:
        next_day = next_day + timedelta(days=1)
        if next_day.weekday() >= 5:
            continue
        try:
            from pandas.tseries.holiday import USFederalHolidayCalendar

            cal = USFederalHolidayCalendar()
            if len(cal.holidays(start=next_day, end=next_day)) > 0:
                continue
        except Exception:
            pass

        if ZoneInfo is None:
            next_open = datetime.combine(next_day, session_open)
        else:
            next_open = datetime.combine(next_day, session_open, tzinfo=ZoneInfo("America/New_York"))
        return False, reason, next_open

# Import existing modules
from quant_agent.questrade_loader import QuestradeAPI
from quant_agent.config_loader import ConfigLoader
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()
ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API')

# PAPER TRADING SAFETY FLAG
PAPER_TRADING = os.getenv('PAPER_TRADING', 'true').lower() in ('1', 'true', 'yes')  # Set to false ONLY when ready for live money

# IMPORTANT SAFETY: This script's main loop is designed for paper execution.
# Live order placement + fill/cancel handling is not implemented here, and the
# exit logic would incorrectly assume fills and mutate "capital" without broker confirmation.
# Use live_order_smoke_test.py for a one-off live order permission check.
if not PAPER_TRADING:
    raise SystemExit(
        "REFUSING TO RUN IN LIVE MODE: test_live_1hour_questrade.py is paper-execution only. "
        "Use live_order_smoke_test.py to validate live trading permissions safely."
    )

# Broker balance snapshot (USD) for dashboard display (Questrade)
broker_cash = None
broker_equity = None
broker_buying_power = None
broker_cash_cad = None
broker_equity_cad = None
broker_buying_power_cad = None

# FRACTIONAL SHARES SUPPORT
FRACTIONAL_SHARES_ENABLED = True  # Questrade supports fractional shares (US stocks only)

# Configuration
INITIAL_CAPITAL = 100000  # Fallback only - will be replaced with live balance

# In paper mode, choose where the bot's working capital comes from.
# - db: use last persisted paper cash balance (capital_after) from Postgres, else INITIAL_CAPITAL
# - broker_cash: use broker cash (USD) from Questrade balances
# - broker_equity: use broker equity (USD) from Questrade balances
# - fixed: use PAPER_CAPITAL_FIXED
PAPER_CAPITAL_SOURCE = os.getenv('PAPER_CAPITAL_SOURCE', 'db').strip().lower()
PAPER_CAPITAL_FIXED = float(os.getenv('PAPER_CAPITAL_FIXED', str(INITIAL_CAPITAL)))
MAX_POSITIONS = 3
BASE_POSITION_SIZE_PCT = 0.25
COMMISSION = 0.0  # Fractional shares are commission-free on Questrade!

# Risk Controls
STOP_LOSS_PCT = 0.05  # 5% stop loss (tighter for small account)
TAKE_PROFIT_PCT = 0.02  # 2% profit target for stocks under $150
HIGH_PRICE_THRESHOLD = 150.0  # Price threshold for dynamic take profit
HIGH_PRICE_TAKE_PROFIT_PCT = 0.01  # 1% profit target for expensive stocks (>$150)
TRAILING_STOP_PCT = 0.015  # 1.5% trailing stop (very tight to lock quick gains)
MIN_VOLUME_RATIO = 0.3  # Relaxed for midday trading
MAX_VOLATILITY = 0.06
MAX_DRAWDOWN_PCT = 0.20  # 20% max drawdown auto-stop
MAX_DAILY_LOSS_PCT = 0.08  # 8% max daily portfolio loss
MAX_CONSECUTIVE_LOSSES = 3  # Pause after 3 losing trades

# FEATURE #1: Per-Trade Position Size Limit (CRITICAL CAPITAL PRESERVATION)
# Prevents disaster: Single bad trade destroying >20% of account in one move
# Example: Without this, a 15% gap down could wipe out 3%+ of portfolio
MAX_POSITION_SIZE_PCT = 0.20  # HARD CAP: Never exceed 20% of capital per trade
SMALL_ACCOUNT_THRESHOLD = 250.0  # Below $250, allow BASE_POSITION_SIZE_PCT flexibility

# Re-entry Controls (AGGRESSIVE MODE - Jan 18-20 monitoring period)
COOLDOWN_MINUTES = 8  # Reduced from 15 for more opportunities
COOLDOWN_AFTER_LOSS_MINUTES = 12  # Reduced from 20 - faster recovery attempts
MIN_PRICE_CHANGE_PCT = 0.007  # 0.7% (reduced from 1%) - catch smaller moves
MIN_MOMENTUM_REENTRY = 0.25  # Reduced from 0.35 - accept moderate signals
# Daily re-entry cap: set to 0 for unlimited re-entries.
MAX_DAILY_REENTRIES = int(os.getenv('MAX_DAILY_REENTRIES', '0'))

# Capital Constraints (for small accounts)
MIN_ACCOUNT_BALANCE = 80.0  # Refuse to trade below this (USD)
USD_CAD_RATE = 0.73  # Approximate conversion rate (1 CAD = 0.73 USD)
# Note: MAX_PRICE_PER_SHARE_PCT removed - fractional shares allow access to all stocks!

# Liquidity Filters
MIN_DOLLAR_VOLUME = 5_000_000  # $5M minimum daily dollar volume
MAX_BID_ASK_SPREAD_PCT = 0.005  # 0.5% max spread

# Market Regime Filters
MAX_VIX = 35  # Pause trading if VIX > 35
SPY_MA_PERIOD = 200  # SPY 200-day moving average

# Trading Schedule
CHECK_INTERVAL_SECONDS = 10  # Check every 10 seconds (6x per minute)
RUN_CONTINUOUS = True  # Set to False for timed tests
REMOTE_STOP_FILE = "logs/STOP_TRADING.txt"  # Create this file to stop trading gracefully
MAX_RUNTIME_MINUTES = float(os.getenv("MAX_RUNTIME_MINUTES", "0"))  # 0 = run until stopped

# FEATURE #2: Time-of-Day Trading Window (avoid chaotic open/close)
# First 5 min: fake breakouts, wide spreads, stop hunts
# Last 5 min: erratic MOC orders, poor execution
TRADING_START_TIME = (9, 35)  # Start at 9:35 AM EST (5 min buffer after open)
TRADING_END_TIME = (15, 55)   # Stop new entries at 3:55 PM EST (5 min before close)

# FEATURE #3: Earnings Blackout Window
# Prevents disaster: Gap moves that ignore stop losses
EARNINGS_BLACKOUT_MINUTES = 30  # Block trades ±30 minutes around earnings

# n8n Webhook Configuration (no hardcoded URLs)
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
N8N_WEBHOOK_ENABLED = os.getenv("N8N_WEBHOOK_ENABLED", "true").lower() in ("1", "true", "yes") and bool(N8N_WEBHOOK_URL)

# Paper execution realism
SLIPPAGE_BPS = float(os.getenv("PAPER_SLIPPAGE_BPS", "2"))  # 2 bps default
PAPER_FILL_DELAY_PROB = float(os.getenv("PAPER_FILL_DELAY_PROB", "0"))
PAPER_PARTIAL_FILL_PROB = float(os.getenv("PAPER_PARTIAL_FILL_PROB", "0"))
PAPER_PARTIAL_FILL_MIN_PCT = float(os.getenv("PAPER_PARTIAL_FILL_MIN_PCT", "0.5"))
PAPER_RANDOM_SEED = os.getenv("PAPER_RANDOM_SEED", "")
DEFAULT_SPREAD_PCT = float(os.getenv("DEFAULT_SPREAD_PCT", "0.002"))

# Quote staleness protection
QUOTE_STALE_SECONDS = int(os.getenv("QUOTE_STALE_SECONDS", "20"))

# Dollar-risk budgeting for small accounts
MAX_DAILY_LOSS_USD = float(os.getenv("MAX_DAILY_LOSS_USD", "5.0"))
RISK_PER_TRADE_USD = float(os.getenv("RISK_PER_TRADE_USD", "0.75"))

# Expanded 55-Stock Universe (Diversified across sectors)
TRADING_UNIVERSE = [
    # Technology - FAANG + Cloud (13 stocks)
    'AAPL', 'AMD', 'CRWD', 'DDOG', 'GOOG', 'META', 'MSFT', 
    'MU', 'NET', 'NVDA', 'PLTR', 'SHOP', 'SNOW',
    
    # Quantum Computing (5 stocks)
    'IONQ', 'LAES', 'QBTS', 'QUBT', 'RGTI',
    
    # Semiconductors (5 stocks)
    'AVGO', 'QCOM', 'TXN', 'ADI', 'AMAT',
    
    # Cybersecurity + AI Infrastructure (5 stocks)
    'PANW', 'ZS', 'OKTA', 'MDB', 'S',
    
    # Healthcare - Pharma + Biotech (7 stocks)
    'ABBV', 'JNJ', 'UNH', 'PFE', 'LLY', 'MRNA', 'TMO',
    
    # Energy (5 stocks)
    'XOM', 'CVX', 'COP', 'EOG', 'SLB',
    
    # Industrials + Aerospace (5 stocks)
    'BA', 'CAT', 'GE', 'HON', 'RTX',
    
    # Consumer Discretionary (7 stocks)
    'AMZN', 'TSLA', 'HD', 'LOW', 'COST', 'TGT', 'NKE',
    
    # Consumer Staples + Entertainment (3 stocks)
    'WMT', 'DIS', 'SBUX',
]

# Sector Exclusions
EXCLUDED_SECTORS = ['Finance', 'Banking', 'Insurance', 'Alcohol', 'Alcoholic Beverages']

# Initialize trade log
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"trades_log_{timestamp}.txt"

# Deterministic RNG for paper fills (optional)
paper_rng = random.Random()
if PAPER_RANDOM_SEED:
    paper_rng.seed(PAPER_RANDOM_SEED)

# Questrade symbol cache
symbol_id_cache = {}
symbol_cache_last_refresh = None
SYMBOL_CACHE_REFRESH_MINUTES = int(os.getenv("SYMBOL_CACHE_REFRESH_MINUTES", "1440"))


def build_symbol_id_cache(tickers, force=False):
    """Cache Questrade symbol IDs to avoid repeated searches."""
    global symbol_id_cache, symbol_cache_last_refresh

    now = datetime.now()
    if not force and symbol_cache_last_refresh:
        age_minutes = (now - symbol_cache_last_refresh).total_seconds() / 60
        if age_minutes < SYMBOL_CACHE_REFRESH_MINUTES:
            return

    missing = [t for t in tickers if t not in symbol_id_cache]
    if not missing and not force:
        return

    log_message(f"   🔎 Caching Questrade symbol IDs for {len(missing)} tickers...")
    for ticker in missing:
        try:
            symbol_id = questrade.search_symbols(ticker)
            if symbol_id:
                symbol_id_cache[ticker] = symbol_id
            else:
                log_message(f"   ⚠️  {ticker}: Symbol not found on Questrade", False)
        except Exception as e:
            log_message(f"   ⚠️  {ticker}: Symbol search failed ({str(e)[:50]})", False)

    symbol_cache_last_refresh = now


def parse_quote_timestamp(quote):
    """Parse available quote timestamp into a datetime, if present."""
    for key in ("lastTradeTime", "quoteTime", "lastTradeDateTime", "lastTradeDateTimeUtc"):
        ts = quote.get(key)
        if not ts:
            continue
        try:
            ts_clean = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(ts_clean)
        except Exception:
            continue
    return None


def compute_mark_price(quote):
    """Compute mark price from bid/ask/last."""
    bid = quote.get("bidPrice") or 0
    ask = quote.get("askPrice") or 0
    last = quote.get("lastTradePrice") or 0
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    if last > 0:
        return last
    if bid > 0:
        return bid
    if ask > 0:
        return ask
    return None


def is_quote_stale(quote, now=None, max_age_seconds=QUOTE_STALE_SECONDS):
    """Return (is_stale, age_seconds). If no timestamp, treat as stale."""
    if not quote:
        return True, None
    if not now:
        now = datetime.now()
    ts = quote.get("timestamp")
    if not ts:
        ts = parse_quote_timestamp(quote)
    if not ts:
        return True, None
    if ts.tzinfo is not None:
        now = datetime.now(ts.tzinfo)
    age_seconds = (now - ts).total_seconds()
    return age_seconds > max_age_seconds, age_seconds


def simulate_paper_fill(ticker, side, shares, quote_data, allow_partial=True):
    """Simulate paper fill using bid/ask and slippage. Returns (filled_shares, fill_price, note) or (None, None, reason)."""
    if not quote_data:
        return None, None, "Missing quote data"

    bid = quote_data.get("bidPrice") or 0
    ask = quote_data.get("askPrice") or 0
    last = quote_data.get("lastTradePrice") or 0

    # Delayed fill simulation (optional)
    if PAPER_FILL_DELAY_PROB > 0 and paper_rng.random() < PAPER_FILL_DELAY_PROB:
        return None, None, "Delayed fill (simulated)"

    # Determine base price
    if side == "BUY":
        if ask > 0:
            base_price = ask
        elif last > 0:
            spread = max(last * DEFAULT_SPREAD_PCT, 0)
            base_price = last + (spread / 2)
        else:
            return None, None, "Missing ask/last for BUY"
        slippage = base_price * (SLIPPAGE_BPS / 10000)
        fill_price = base_price + slippage
    else:
        if bid > 0:
            base_price = bid
        elif last > 0:
            spread = max(last * DEFAULT_SPREAD_PCT, 0)
            base_price = last - (spread / 2)
        else:
            return None, None, "Missing bid/last for SELL"
        slippage = base_price * (SLIPPAGE_BPS / 10000)
        fill_price = max(base_price - slippage, 0)

    filled_shares = shares
    note = "Fill"

    # Partial fill simulation (optional)
    if allow_partial and PAPER_PARTIAL_FILL_PROB > 0 and paper_rng.random() < PAPER_PARTIAL_FILL_PROB:
        partial_pct = min(max(PAPER_PARTIAL_FILL_MIN_PCT, 0.1), 0.9)
        fill_fraction = paper_rng.uniform(partial_pct, 0.9)
        filled_shares = shares * fill_fraction
        note = f"Partial fill ({fill_fraction:.0%})"

    if not FRACTIONAL_SHARES_ENABLED:
        filled_shares = int(filled_shares)

    if filled_shares <= 0:
        return None, None, "Partial fill too small"

    return filled_shares, fill_price, note



def log_message(message, print_too=True):
    """Write message to log file and optionally print"""
    with open(log_file, 'a', encoding='utf-8', errors='replace') as f:
        f.write(f"{message}\n")
    if print_too:
        try:
            print(message)
        except UnicodeEncodeError:
            # Windows console can't handle some emojis, sanitize them
            print(message.encode('ascii', errors='replace').decode('ascii'))

def print_header(text):
    """Print formatted header"""
    line = "=" * 80
    msg = f"\n{line}\n{text}\n{line}"
    log_message(msg)

def print_alert(message, emoji="🔔"):
    """Print alert with timestamp"""
    timestamp = datetime.now().strftime('%I:%M:%S %p')
    msg = f"\n{emoji} [{timestamp}] {message}"
    log_message(msg)

def send_webhook(trade_data):
    """Send trade alert to n8n webhook"""
    if not N8N_WEBHOOK_ENABLED:
        return
    
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=trade_data,
            timeout=5
        )
        if response.status_code == 200:
            log_message(f"   ✓ Webhook sent: {trade_data['action']} {trade_data['ticker']}", False)
        else:
            log_message(f"   ⚠️ Webhook failed: {response.status_code}", False)
    except Exception as e:
        log_message(f"   ⚠️ Webhook error: {str(e)[:50]}", False)

def send_error_alert(error_type, details, critical=False):
    """Send error alert to Discord via webhook"""
    if not N8N_WEBHOOK_ENABLED:
        return
    
    emoji = "🚨" if critical else "⚠️"
    timestamp = datetime.now().strftime('%I:%M:%S %p')
    
    error_data = {
        "action": "ERROR",
        "error_type": error_type,
        "details": details,
        "critical": critical,
        "timestamp": timestamp,
        "message": f"{emoji} **{error_type}**\n{details}\nTime: {timestamp}"
    }
    
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=error_data,
            timeout=5
        )
        if response.status_code == 200:
            log_message(f"   ✓ Error alert sent: {error_type}", False)
    except Exception as e:
        log_message(f"   ⚠️ Error alert failed: {str(e)[:50]}", False)

# Database connection
def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        # Read database credentials from .env
        load_dotenv()
        db_password = os.getenv('DB_PASSWORD', '')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_name = os.getenv('DB_NAME', 'tradeagent')
        db_user = os.getenv('DB_USER', 'postgres')
        
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        log_message(f"❌ Database connection failed: {e}")
        send_error_alert("Database Connection Failed", str(e), critical=True)
        return None

def save_position_to_db(ticker, position_data):
    """Save or update position in PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO positions 
                (ticker, quantity, entry_price, entry_date, current_price,
                 stop_loss, take_profit, max_hold_days, position_value,
                 unrealized_pnl, unrealized_pnl_pct, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (ticker) DO UPDATE SET
                    quantity = EXCLUDED.quantity,
                    current_price = EXCLUDED.current_price,
                    position_value = EXCLUDED.position_value,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    unrealized_pnl_pct = EXCLUDED.unrealized_pnl_pct,
                    stop_loss = EXCLUDED.stop_loss,
                    take_profit = EXCLUDED.take_profit,
                    updated_at = NOW()
            """, (
                ticker,
                position_data['shares'],
                position_data['entry_price'],
                position_data['entry_date'],
                position_data.get('current_price', position_data['entry_price']),
                position_data['stop_loss'],
                position_data['take_profit'],
                position_data.get('max_hold_days', 30),
                position_data['shares'] * position_data.get('current_price', position_data['entry_price']),
                position_data.get('unrealized_pnl', 0),
                position_data.get('unrealized_pnl_pct', 0)
            ))
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        log_message(f"   ⚠️ Failed to save position to DB: {str(e)[:100]}", False)
        conn.close()
        return False

def delete_position_from_db(ticker):
    """Delete position from PostgreSQL after exit"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM positions WHERE ticker = %s", (ticker,))
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        log_message(f"   ⚠️ Failed to delete position from DB: {str(e)[:100]}", False)
        conn.close()
        return False

def load_positions_from_db():
    """Load positions from PostgreSQL on startup"""
    conn = get_db_connection()
    if not conn:
        return {}
    
    positions = {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ticker, quantity, entry_price, entry_date, current_price,
                       stop_loss, take_profit, unrealized_pnl, unrealized_pnl_pct
                FROM positions
                WHERE exit_triggered = FALSE
                ORDER BY entry_date DESC
            """)
            rows = cur.fetchall()
            
            for row in rows:
                positions[row['ticker']] = {
                    'shares': row['quantity'],
                    'entry_price': float(row['entry_price']),
                    'entry_date': row['entry_date'],
                    'entry_time': row['entry_date'],  # Use entry_date for hold duration calculation
                    'current_price': float(row['current_price']),
                    'stop_loss': float(row['stop_loss']),
                    'take_profit': float(row['take_profit']),
                    'highest_price': float(row['current_price']),
                    'trailing_stop': float(row['current_price']) * (1 - TRAILING_STOP_PCT),
                    'unrealized_pnl': float(row.get('unrealized_pnl', 0)),
                    'unrealized_pnl_pct': float(row.get('unrealized_pnl_pct', 0))
                }
        
        conn.close()
        log_message(f"✅ Loaded {len(positions)} positions from database")
        return positions
    except Exception as e:
        log_message(f"⚠️ Failed to load positions from DB: {str(e)[:100]}")
        send_error_alert("Position Load Failed", str(e), critical=True)
        conn.close()
        return {}

def log_trade_to_db(ticker, action, shares, price, capital_before, total_positions, 
                    exit_reason=None, entry_price=None, hold_minutes=None, pnl=None, pnl_pct=None, notes=None):
    """Log every trade (buy/sell) to trades_history table"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        total_value = float(shares) * float(price)
        if action == 'BUY':
            capital_after = float(capital_before) - total_value
        else:
            capital_after = float(capital_before) + total_value

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trades_history 
                (ticker, action, shares, price, total_value, 
                 exit_reason, entry_price, hold_duration_minutes, pnl, pnl_pct,
                 capital_before, capital_after, total_positions, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ticker,
                    action,
                    shares,
                    price,
                    total_value,
                    exit_reason,
                    entry_price,
                    hold_minutes,
                    pnl,
                    pnl_pct,
                    capital_before,
                    capital_after,
                    total_positions,
                    notes,
                ),
            )
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        log_message(f"   ⚠️ Failed to log trade to history: {str(e)[:100]}", False)
        try:
            conn.close()
        except Exception:
            pass
        return False

def load_last_capital_after_from_db(fallback_capital: float) -> float:
    """Load last known paper-trading cash balance from trades_history.

    In PAPER_TRADING mode, broker balances are not authoritative because positions
    are tracked in Postgres. We persist cash via capital_after on each trade.
    """
    conn = get_db_connection()
    if not conn:
        return float(fallback_capital)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT capital_after
                FROM trades_history
                WHERE capital_after IS NOT NULL
                ORDER BY trade_date DESC
                LIMIT 1
            """)
            row = cur.fetchone()
        conn.close()
        if row and row[0] is not None:
            return float(row[0])
        return float(fallback_capital)
    except Exception as e:
        log_message(f"   ⚠️ Failed to load last capital from DB: {str(e)[:100]}", False)
        try:
            conn.close()
        except Exception:
            pass
        return float(fallback_capital)

# Trading mode indicator
trading_mode = "🧪 PAPER TRADING MODE" if PAPER_TRADING else "💰 LIVE TRADING MODE"

print_header(f"🔴 LIVE TRADING - QUESTRADE - {trading_mode}")

# PRE-FLIGHT CHECK #1: Weekend Check
today = get_now_eastern()
is_open_now, market_reason, next_open_dt = get_us_market_state(today)
if not is_open_now:
    log_message(f"\n⛔ MARKET CLOSED: {market_reason}")
    log_message(f"   Current time (ET): {today.strftime('%I:%M %p')}")
    if next_open_dt is not None:
        log_message(f"   Next open: {next_open_dt.strftime('%a %m/%d %I:%M %p ET')}")
    if os.getenv('EXIT_IF_MARKET_CLOSED', '0') == '1':
        log_message("   EXIT_IF_MARKET_CLOSED=1 -> exiting\n")
        exit(0)
    log_message("   Bot will idle until market opens (no entries will be placed).\n")

# Initialize
start_time = datetime.now()
starting_equity = INITIAL_CAPITAL  # Will be updated with live balance
daily_start_equity = INITIAL_CAPITAL  # Track for daily loss limiter
consecutive_losses = 0  # Track losing streak
total_closed_trades = 0  # For loss tracking
market_regime_ok = True  # Market condition flag
max_drawdown_pct = 0.0  # Track worst drawdown during session

# Re-entry control tracking
last_sell_times = {}  # {ticker: datetime} - when we last sold this stock
last_sell_prices = {}  # {ticker: price} - price we sold at
last_sell_was_loss = {}  # {ticker: bool} - whether last sell was a loss (for stricter cooldown)
daily_reentry_count = {}  # {ticker: count} - how many times re-entered today

# API token refresh tracking
token_refresh_time = datetime.now()  # Track when we last refreshed
TOKEN_REFRESH_INTERVAL_MINUTES = 25  # Refresh before 30-min expiry

# Last known prices fallback (for API failures)
last_known_prices = {}  # Store last successful price fetch
last_known_quotes = {}  # Store last successful quote map
last_quote_fetch_error = None  # Last known quote-fetch error for dashboard/status

# Quote freshness / feed-degraded counters (reported EOD + optionally via dashboard status)
trade_block_stats = {
    'entries_paused_cache_cycles': 0,
    'entries_paused_stale_positions_cycles': 0,
    'entry_block_missing_quote': 0,
    'entry_block_stale_quote': 0,
    'exit_block_stale_or_missing_quote': 0,
}

log_message(f"\n⏰ Start Time: {start_time.strftime('%I:%M:%S %p EST')}")
log_message(f"🎚️ Trading Mode: {trading_mode}")
log_message(f"📊 Max Positions: {MAX_POSITIONS}")
log_message(f"🔄 Check Interval: {CHECK_INTERVAL_SECONDS} seconds")
log_message(f"📝 Trade Log: {log_file}")
log_message(f"🛑 Remote Stop: Create '{REMOTE_STOP_FILE}' to stop gracefully")
log_message(f"⚠️  Or press Ctrl+C to stop immediately")

log_message(f"\n📋 Trading Universe: {len(TRADING_UNIVERSE)} stocks")
log_message(f"   {', '.join(TRADING_UNIVERSE)}")

# Initialize Questrade API
try:
    log_message("\n🔌 Connecting to Questrade API...")
    questrade = QuestradeAPI()
    token_refresh_time = datetime.now()  # Record initial authentication time
    log_message("✅ Connected to Questrade successfully!")
    log_message(f"   Server: {questrade.api_server}")
    log_message(f"   Mode: {questrade.server_type}")
    log_message(f"   Token will auto-refresh every {TOKEN_REFRESH_INTERVAL_MINUTES} minutes")

    # Build symbol cache once at startup
    build_symbol_id_cache(TRADING_UNIVERSE, force=True)
except Exception as e:
    error_msg = f"Failed to connect to Questrade: {str(e)}"
    log_message(f"❌ {error_msg}")
    log_message("   Please check your .env file has valid QUESTRADE_REFRESH_TOKEN")
    send_error_alert("Questrade Connection Failed", error_msg, critical=True)
    exit(1)

# Get account balance
try:
    log_message("\n💰 Fetching account balance...")
    accounts = questrade.get_accounts()
    if not accounts:
        raise Exception("No accounts found")
    
    account_number = accounts[0]['number']
    log_message(f"   Account: {account_number} ({accounts[0]['type']})")
    
    balances = questrade.get_balances(account_number)
    if not balances:
        raise Exception("Could not retrieve balances")
    
    # Get CAD balances (Questrade returns CAD for Canadian accounts)
    live_cash_cad = float(balances.get('cash', 0))
    live_equity_cad = float(balances.get('totalEquity', 0))
    buying_power_cad = float(balances.get('buyingPower', 0))
    
    # Convert to USD for US stock trading
    live_cash = live_cash_cad * USD_CAD_RATE
    live_equity = live_equity_cad * USD_CAD_RATE
    buying_power = buying_power_cad * USD_CAD_RATE

    # Persist broker snapshot for dashboard
    broker_cash_cad = live_cash_cad
    broker_equity_cad = live_equity_cad
    broker_buying_power_cad = buying_power_cad
    broker_cash = live_cash
    broker_equity = live_equity
    broker_buying_power = buying_power
    
    # Set working capital / equity base
    if PAPER_TRADING:
        if PAPER_CAPITAL_SOURCE in ('broker', 'broker_cash'):
            capital = live_cash
        elif PAPER_CAPITAL_SOURCE == 'broker_equity':
            capital = live_equity
        elif PAPER_CAPITAL_SOURCE == 'fixed':
            capital = float(PAPER_CAPITAL_FIXED)
        else:
            # Default: pull last known paper cash from DB (falls back to INITIAL_CAPITAL)
            capital = load_last_capital_after_from_db(INITIAL_CAPITAL)
        starting_equity = capital
        daily_start_equity = capital
    else:
        # For live trading, treat cash as available buying capital.
        capital = live_cash
        starting_equity = live_equity
        daily_start_equity = live_equity  # Set daily starting point
    
    log_message(f"   💵 Cash: CAD ${live_cash_cad:,.2f} (USD ${live_cash:,.2f})")
    log_message(f"   📈 Total Equity: CAD ${live_equity_cad:,.2f} (USD ${live_equity:,.2f})")
    log_message(f"   💪 Buying Power: CAD ${buying_power_cad:,.2f} (USD ${buying_power:,.2f})")
    log_message(f"   🔄 Conversion Rate: 1 CAD = {USD_CAD_RATE} USD")
    
    # PRE-FLIGHT SAFETY CHECK #1: Minimum balance
    if capital < MIN_ACCOUNT_BALANCE:
        error_msg = f"Account balance ${capital:.2f} below minimum ${MIN_ACCOUNT_BALANCE:.2f}"
        log_message(f"\n🚨 SAFETY CHECK FAILED: {error_msg}")
        send_error_alert("Insufficient Capital", error_msg, critical=True)
        exit(1)
    
    log_message(f"   ✅ Balance check passed (>${MIN_ACCOUNT_BALANCE})")
    
    # PRE-FLIGHT INFO: Capital allocation with fractional shares
    log_message(f"\n💎 FRACTIONAL SHARES ENABLED:")
    log_message(f"   📊 Total Capital: ${capital:.2f}")
    log_message(f"   💰 Position Size: ${capital / MAX_POSITIONS:.2f} each ({BASE_POSITION_SIZE_PCT:.0%} of capital)")
    log_message(f"   🎯 Max Positions: {MAX_POSITIONS}")
    log_message(f"   ✨ Commission: ${COMMISSION:.2f} (FREE for fractional shares!)")
    log_message(f"   🌟 All {len(TRADING_UNIVERSE)} stocks tradeable regardless of price")
    
except Exception as e:
    error_msg = f"Failed to fetch account balance: {str(e)}"
    log_message(f"❌ {error_msg}")
    log_message(f"   Using fallback capital: ${INITIAL_CAPITAL:,}")
    send_error_alert("Balance Fetch Failed", error_msg, critical=False)
    if PAPER_TRADING and PAPER_CAPITAL_SOURCE == 'fixed':
        capital = float(PAPER_CAPITAL_FIXED)
    else:
        capital = load_last_capital_after_from_db(INITIAL_CAPITAL) if PAPER_TRADING else INITIAL_CAPITAL
    starting_equity = capital

    broker_cash = None
    broker_equity = None
    broker_buying_power = None
    broker_cash_cad = None
    broker_equity_cad = None
    broker_buying_power_cad = None

# Load historical data for momentum calculation
print_header("📊 LOADING HISTORICAL DATA")
historical_data = {}
data_dir = "historical_data"
for ticker in TRADING_UNIVERSE:
    csv_file = os.path.join(data_dir, f"historical_data_{ticker}.csv")
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file, index_col='Date', parse_dates=True)
        historical_data[ticker] = df
        log_message(f"  ✓ {ticker}: {len(df)} days")
    else:
        log_message(f"  ⚠️  {ticker}: No historical data file")

log_message(f"\n✅ Loaded {len(historical_data)} stocks")

# PRE-FLIGHT SAFETY CHECK #2: Data freshness
try:
    most_recent_date = max([df.index[-1] for df in historical_data.values()])
    today = datetime.now().date()
    last_data_date = most_recent_date.date()
    data_age_days = (today - last_data_date).days

    # Use business days so long weekends/US market holidays do not cause false alarms
    business_days_since = None
    try:
        from pandas.tseries.holiday import USFederalHolidayCalendar
        from pandas.tseries.offsets import CustomBusinessDay

        cbd = CustomBusinessDay(calendar=USFederalHolidayCalendar())
        business_days_since = len(pd.date_range(last_data_date + timedelta(days=1), today, freq=cbd))
    except Exception:
        business_days_since = None

    # Defaults are intentionally tolerant to long weekends/holidays.
    max_calendar_gap = int(os.getenv('MAX_HISTORICAL_DATA_CALENDAR_DAYS', '7'))
    max_business_gap = int(os.getenv('MAX_HISTORICAL_DATA_BUSINESS_DAYS', '4'))

    too_old = False
    if business_days_since is not None:
        too_old = business_days_since > max_business_gap
    else:
        too_old = data_age_days > max_calendar_gap

    if too_old:
        age_detail = f"{data_age_days} calendar days"
        if business_days_since is not None:
            age_detail += f" / {business_days_since} business days"
        error_msg = f"Historical data is {age_detail} old (last: {last_data_date})"
        log_message(f"\n🚨 SAFETY CHECK FAILED: {error_msg}")
        log_message("   Run download_historical_data.py to update data before trading")
        send_error_alert("Stale Data Detected", error_msg, critical=True)
        exit(1)

    freshness_note = f"{data_age_days} days old"
    if business_days_since is not None:
        freshness_note += f" / {business_days_since} business days"
    log_message(f"   ✅ Data freshness check passed (last update: {last_data_date}, {freshness_note})")
except Exception as e:
    log_message(f"⚠️ Could not verify data freshness: {str(e)}")

# Load existing positions from database
log_message("\n💾 Loading positions from database...")
positions = load_positions_from_db()
starting_positions_count = len(positions)
trades = []
checks = 0

# In paper trading, compute an equity baseline using persisted cash + loaded positions.
# This prevents double-counting and makes session P&L truthful across restarts.
if PAPER_TRADING and starting_positions_count:
    positions_value = 0.0
    for _ticker, _pos in positions.items():
        px = float(_pos.get('current_price') or _pos.get('entry_price') or 0.0)
        positions_value += float(_pos.get('shares') or 0.0) * px
    starting_equity = float(capital) + positions_value
    daily_start_equity = starting_equity
    log_message(f"   🧾 Paper baseline: Cash ${capital:,.2f} + Positions ${positions_value:,.2f} = Equity ${starting_equity:,.2f}")

if positions:
    log_message(f"   📁 Found {len(positions)} open positions:")
    for ticker, pos in positions.items():
        pnl_pct = pos.get('unrealized_pnl_pct', 0)
        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
        shares_str = f"{pos['shares']:.4f}" if pos['shares'] < 1 else f"{pos['shares']:.2f}"
        log_message(f"      {pnl_emoji} {ticker}: {shares_str} shares @ ${pos['entry_price']:.2f} ({pnl_pct:+.1f}%)")
    
    # POSITION RECONCILIATION: Compare DB vs Broker (SKIP in paper trading mode)
    if PAPER_TRADING:
        log_message("\n🧪 Paper Trading Mode: Skipping broker reconciliation")
        log_message("   (Paper positions exist only in database)")
    else:
        try:
            log_message("\n🔍 Reconciling positions with broker...")
            broker_positions = questrade.get_positions(account_number)
            broker_tickers = {p['symbol'] for p in broker_positions}
            db_tickers = set(positions.keys())
            
            # Check for discrepancies
            only_in_db = db_tickers - broker_tickers
            only_in_broker = broker_tickers - db_tickers
            
            if only_in_db or only_in_broker:
                error_msg = f"POSITION MISMATCH! DB: {db_tickers}, Broker: {broker_tickers}"
                log_message(f"\n🚨 {error_msg}")
                if only_in_db:
                    log_message(f"   Only in DB: {only_in_db}")
                if only_in_broker:
                    log_message(f"   Only in Broker: {only_in_broker}")
                send_error_alert("Position Reconciliation Failed", error_msg, critical=True)
                log_message("\n⏸️ Trading paused - manual intervention required")
                log_message("   Fix positions in database or broker, then restart")
                exit(1)
            else:
                log_message(f"   ✅ Reconciliation passed: {len(positions)} positions match")
        except Exception as e:
            error_msg = f"Position reconciliation error: {str(e)}"
            log_message(f"⚠️ {error_msg}")
            send_error_alert("Reconciliation Error", error_msg, critical=False)
else:
    log_message("   🆕 No open positions - starting fresh")

def calculate_momentum_score(df, current_price=None):
    """Calculate momentum score from historical data and current price"""
    if len(df) < 60:
        return None, None, None
    
    close = df['Close']
    volume = df['Volume']
    
    # If we have current price, use it for today's return
    last_close = close.iloc[-1]
    if current_price:
        # Today's intraday return
        today_return = (current_price - last_close) / last_close
    else:
        today_return = 0
    
    # Returns from historical data
    returns_20d = close.pct_change(20).iloc[-1]
    returns_60d = close.pct_change(60).iloc[-1]
    
    # Momentum score (include today's action with higher weight)
    momentum = 0.3 * returns_20d + 0.3 * returns_60d + 0.4 * today_return
    
    # Volume ratio (from last historical day)
    volume_ma20 = volume.rolling(20).mean().iloc[-1]
    volume_ratio = volume.iloc[-1] / volume_ma20 if volume_ma20 > 0 else 0
    
    # Volatility
    returns = close.pct_change()
    volatility = returns.rolling(20).std().iloc[-1]
    
    return momentum, volume_ratio, volatility


def get_current_prices_questrade(tickers):
    """Get current prices and full quotes from Questrade."""
    global last_quote_fetch_error
    prices = {}
    quote_map = {}
    errors = []

    # Reset per-call
    last_quote_fetch_error = None

    try:
        # Ensure symbol cache is populated
        build_symbol_id_cache(tickers)

        symbol_ids = {t: sid for t, sid in symbol_id_cache.items() if t in tickers}
        if len(symbol_ids) == 0:
            error_msg = "No cached symbols found on Questrade - check API access"
            last_quote_fetch_error = error_msg
            log_message(f"   ⚠️  {error_msg}", False)
            send_error_alert("Symbol Lookup Failed", error_msg, critical=True)
            return prices, quote_map

        # Get quotes for all symbols
        try:
            symbol_id_list = list(symbol_ids.values())
            quotes = questrade.get_quotes(symbol_id_list)

            id_to_ticker = {v: k for k, v in symbol_ids.items()}
            for quote in quotes:
                ticker = id_to_ticker.get(quote.get('symbolId'))
                if not ticker:
                    continue

                quote_data = {
                    'lastTradePrice': quote.get('lastTradePrice'),
                    'bidPrice': quote.get('bidPrice'),
                    'askPrice': quote.get('askPrice'),
                    'volume': quote.get('volume'),
                    'timestamp': parse_quote_timestamp(quote)
                }
                quote_map[ticker] = quote_data

                mark_price = compute_mark_price(quote_data)
                if mark_price is not None:
                    prices[ticker] = float(mark_price)

        except Exception as e:
            error_msg = f"Quote fetch failed: {str(e)[:100]}"
            last_quote_fetch_error = error_msg
            log_message(f"⚠️  {error_msg}", False)
            send_error_alert("API Quote Error", error_msg, critical=True)

    except Exception as e:
        error_msg = f"Error fetching prices: {str(e)[:100]}"
        last_quote_fetch_error = error_msg
        log_message(f"⚠️  {error_msg}", False)
        send_error_alert("Price Fetch Failed", error_msg, critical=True)

    return prices, quote_map

def check_market_regime():
    """Check if market conditions are safe for trading (VIX < 35, SPY above 200MA)"""
    try:
        # For now, always return True - VIX/SPY checks require additional data source
        # TODO: Implement VIX check from CBOE or integrate with data provider
        return True, "Market regime check disabled (VIX/SPY data not configured)"
    except Exception as e:
        log_message(f"⚠️ Market regime check failed: {str(e)[:100]}", False)
        return True, f"Check failed: {str(e)[:50]}"

def check_liquidity(ticker, quote_data):
    """Check if stock has sufficient liquidity (dollar volume > $5M, spread < 0.5%)"""
    try:
        # Get bid/ask from quote
        if not quote_data:
            return False, "Missing quote data"

        bid = quote_data.get('bidPrice') or 0
        ask = quote_data.get('askPrice') or 0
        last_price = quote_data.get('lastTradePrice') or 0
        volume = quote_data.get('volume') or 0

        mark_price = compute_mark_price(quote_data)
        if not mark_price or volume <= 0:
            return False, "Missing price/volume for liquidity"

        # Calculate dollar volume (rough estimate using mark price)
        dollar_volume = volume * mark_price
        
        # Calculate bid-ask spread percentage
        if bid > 0 and ask > 0:
            spread_pct = (ask - bid) / ((ask + bid) / 2)
        else:
            spread_pct = 0
        
        # Check filters
        if dollar_volume < MIN_DOLLAR_VOLUME:
            return False, f"Low volume: ${dollar_volume/1_000_000:.1f}M < ${MIN_DOLLAR_VOLUME/1_000_000:.0f}M"
        
        if spread_pct > MAX_BID_ASK_SPREAD_PCT:
            return False, f"Wide spread: {spread_pct*100:.2f}% > {MAX_BID_ASK_SPREAD_PCT*100:.1f}%"
        
        return True, "Pass"
    except Exception as e:
        # If liquidity check fails, allow trade but log warning
        log_message(f"⚠️ Liquidity check failed for {ticker}: {str(e)[:50]}", False)
        return True, "Check failed"

def filter_affordable_stocks(prices, max_capital):
    """With fractional shares, all stocks are affordable - just return all prices"""
    if FRACTIONAL_SHARES_ENABLED:
        # Fractional shares = no affordability filter needed!
        log_message(f"   💎 Fractional shares enabled - all {len(prices)} stocks tradeable", False)
        return prices
    
    # Legacy whole-share logic (kept for reference, but not used)
    max_price_per_share = max_capital * 0.30
    affordable = {ticker: price for ticker, price in prices.items() if price <= max_price_per_share}
    
    if len(affordable) == 0:
        error_msg = f"No affordable stocks! All above ${max_price_per_share:.2f}/share"
        log_message(f"\n🚨 {error_msg}")
        send_error_alert("No Affordable Stocks", error_msg, critical=True)
    
    return affordable

def validate_position_size(ticker, shares, price, current_capital):
    """
    FEATURE #1: CRITICAL SAFETY CHECK - Per-Trade Position Size Limit
    
    This prevents a single bad trade from destroying your account.
    
    DISASTER PREVENTED:
    - Without this: $1000 account, buy $250 of stock (25%), gaps down 15% = $37.50 loss = 3.75% account loss
    - With this: Capped at $200 (20%), same gap = $30 loss = 3% account loss
    - Multiple bad trades without limit = account wipeout in hours
    
    Args:
        ticker: Stock symbol
        shares: Number of shares to buy
        price: Current price per share
        current_capital: Total available capital
    
    Returns:
        (is_valid, adjusted_value): Tuple of validation result and max allowed value
    """
    position_value = shares * price
    position_pct = position_value / current_capital if current_capital > 0 else 0
    
    # Calculate maximum allowed position value
    if current_capital < SMALL_ACCOUNT_THRESHOLD:
        # Small account: Use BASE_POSITION_SIZE_PCT for flexibility
        max_allowed_pct = BASE_POSITION_SIZE_PCT
    else:
        # Larger account: Enforce strict 20% limit
        max_allowed_pct = MAX_POSITION_SIZE_PCT
    
    max_allowed_value = current_capital * max_allowed_pct
    
    # Validate position size
    if position_value > max_allowed_value:
        log_message(f"\n🚨 POSITION SIZE VIOLATION DETECTED for {ticker}:")
        log_message(f"   Attempted Position: ${position_value:.2f} ({position_pct:.1%} of capital)")
        log_message(f"   Maximum Allowed: ${max_allowed_value:.2f} ({max_allowed_pct:.0%} limit)")
        log_message(f"   Account Size: ${current_capital:.2f}")
        log_message(f"   🛑 BLOCKING THIS TRADE - position exceeds safety limit")
        log_message(f"   Reason: Prevents single trade from destroying >{max_allowed_pct:.0%} of account")
        
        # Send critical alert
        send_error_alert(
            "Position Size Safety Violation",
            f"{ticker}: Attempted ${position_value:.2f} ({position_pct:.1%}) exceeds {max_allowed_pct:.0%} limit",
            critical=True
        )
        
        return False, max_allowed_value
    
    # Position size is safe
    log_message(f"   ✅ Position size check passed: ${position_value:.2f} ({position_pct:.1%} of ${current_capital:.2f})")
    return True, position_value

def is_within_trading_window():
    """
    FEATURE #2: Time-of-Day Trading Window Check
    
    Block trades during chaotic open/close periods.
    
    DISASTER PREVENTED:
    - First 5 min (9:30-9:35): Fake breakouts, wide spreads, stop hunts
    - Last 5 min (3:55-4:00): Erratic MOC orders, poor execution prices
    - Professional traders avoid these windows for good reason
    
    Returns:
        (is_valid, reason): Tuple of boolean and explanation string
    """
    now = get_now_eastern()
    current_time = now.time()
    
    # Unpack trading window times
    start_hour, start_min = TRADING_START_TIME
    end_hour, end_min = TRADING_END_TIME
    
    trading_start = time(start_hour, start_min)
    trading_end = time(end_hour, end_min)
    
    # Check if before trading window
    if current_time < trading_start:
        return False, f"Before {start_hour}:{start_min:02d} AM (avoiding open volatility)"
    
    # Check if after trading window
    if current_time >= trading_end:
        return False, f"After {end_hour}:{end_min:02d} PM (avoiding close volatility)"
    
    return True, "Within trading window"

def check_earnings_blackout(ticker):
    """
    FEATURE #3: Earnings Blackout Check
    
    Block trades ±30 minutes around earnings announcements.
    
    DISASTER PREVENTED:
    - Stocks gap 10-20% on earnings regularly
    - Your 5% stop loss becomes meaningless on a 15% gap
    - No technical signal can predict earnings surprises
    - Even intraday, earnings can hit during session causing halts/gaps
    
    Args:
        ticker: Stock symbol to check
    
    Returns:
        (is_blocked, reason): Tuple of boolean and explanation string
    """
    if not ALPHAVANTAGE_API_KEY:
        # If no API key, fail-open (allow trade with warning)
        return False, "Alpha Vantage API key not configured (check skipped)"
    
    try:
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Alpha Vantage earnings calendar endpoint (CSV format)
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'EARNINGS_CALENDAR',
            'horizon': '3month',
            'apikey': ALPHAVANTAGE_API_KEY
        }
        
        # Make API request with timeout
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            # API error - fail-open but log warning
            log_message(f"   ⚠️ Earnings API returned {response.status_code} - proceeding without check")
            return False, f"API error {response.status_code} (allowing trade)"
        
        # Parse CSV response
        import csv
        from io import StringIO
        
        csv_data = StringIO(response.text)
        reader = csv.DictReader(csv_data)
        
        # Check if ticker has earnings today
        for row in reader:
            if row.get('symbol', '').upper() == ticker.upper():
                report_date = row.get('reportDate', '')
                
                # Check if report date is today
                if report_date == today:
                    earnings_time = row.get('timeOfTheDay', '').lower().strip()
                    
                    # If earnings time is specified, check timing
                    if earnings_time:
                        if 'post' in earnings_time or 'after' in earnings_time:
                            # Earnings after close - safe to trade during day
                            return False, f"Earnings after close today (safe to trade)"
                        elif 'pre' in earnings_time or 'before' in earnings_time:
                            # Earnings before open - already happened, but might still be volatile
                            return True, f"Earnings reported this morning (avoiding volatility)"
                        else:
                            # Other time specified - block for safety
                            return True, f"Earnings TODAY at {earnings_time} (±{EARNINGS_BLACKOUT_MINUTES}min blackout)"
                    else:
                        # No time specified - block to be safe
                        return True, f"Earnings scheduled TODAY (time unknown - blocking)"
        
        # No earnings found for this ticker today
        return False, "No earnings today"
    
    except requests.Timeout:
        log_message(f"   ⚠️ Earnings API timeout for {ticker} - proceeding without check")
        return False, "API timeout (allowing trade)"
    except Exception as e:
        log_message(f"   ⚠️ Earnings check error for {ticker}: {str(e)}")
        return False, f"Check failed: {str(e)} (allowing trade)"

def check_positions(current_prices, quote_map=None):
    """Check existing positions for exits"""
    global capital, positions, trades, consecutive_losses, total_closed_trades
    global last_sell_times, last_sell_prices, last_sell_was_loss, daily_reentry_count  # Add cooldown tracking
    global trade_block_stats
    
    exits = []
    for ticker, pos in list(positions.items()):
        quote_data = quote_map.get(ticker) if quote_map else None
        is_stale, age_seconds = is_quote_stale(quote_data)
        if is_stale:
            age_msg = "no timestamp" if age_seconds is None else f"{age_seconds:.0f}s old"
            log_message(f"   🚫 {ticker}: Exit checks paused (stale/missing quote: {age_msg})", False)
            trade_block_stats['exit_block_stale_or_missing_quote'] += 1
            continue

        current_price = compute_mark_price(quote_data)
        if current_price is None:
            if ticker not in current_prices:
                log_message(f"   ⚠️ {ticker}: No mark price + no fallback price; skipping exit checks", False)
                continue
            current_price = current_prices[ticker]
        
        # Update highest price and trailing stop
        if current_price > pos['highest_price']:
            pos['highest_price'] = current_price
            pos['trailing_stop'] = current_price * (1 - TRAILING_STOP_PCT)
        
        # Check stop loss
        if current_price <= pos['stop_loss']:
            exits.append((ticker, current_price, 'stop_loss'))
        # Check take profit
        elif current_price >= pos['take_profit']:
            exits.append((ticker, current_price, 'take_profit'))
        # Check trailing stop
        elif current_price <= pos['trailing_stop']:
            exits.append((ticker, current_price, 'trailing_stop'))
    
    # Execute exits
    for ticker, exit_price, reason in exits:
        pos = positions[ticker]
        if PAPER_TRADING:
            quote_data = quote_map.get(ticker) if quote_map else None
            filled_shares, fill_price, fill_note = simulate_paper_fill(ticker, "SELL", pos['shares'], quote_data, allow_partial=False)
            if fill_price:
                exit_price = fill_price
            else:
                log_message(f"   ⚠️ {ticker}: Exit fill fallback to mark ({fill_note})", False)

        exit_value = pos['shares'] * exit_price - COMMISSION
        capital += exit_value
        
        pnl = exit_value - (pos['shares'] * pos['entry_price'] + COMMISSION)
        pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
        
        # Calculate hold duration
        hold_minutes = int((datetime.now() - pos['entry_time']).total_seconds() / 60)
        
        # Log trade to history
        log_trade_to_db(
            ticker=ticker,
            action='SELL',
            shares=pos['shares'],
            price=exit_price,
            capital_before=capital - exit_value,  # Capital before this sell
            total_positions=len(positions) - 1,  # Will be one less after deletion
            exit_reason=reason,
            entry_price=pos['entry_price'],
            hold_minutes=hold_minutes,
            pnl=pnl,
            pnl_pct=pnl_pct,
            notes=f"Exit: {reason.replace('_', ' ').title()}"
        )
        
        # Track consecutive losses
        total_closed_trades += 1
        if pnl < 0:
            consecutive_losses += 1
        else:
            consecutive_losses = 0  # Reset on winning trade
        
        trade = {
            'time': datetime.now().strftime('%I:%M:%S %p'),
            'action': 'SELL',
            'ticker': ticker,
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'shares': pos['shares'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        }
        trades.append(trade)
        
        # ===== TRACK SELL FOR RE-ENTRY COOLDOWN =====
        last_sell_times[ticker] = datetime.now()
        last_sell_prices[ticker] = exit_price
        last_sell_was_loss[ticker] = (pnl < 0)  # Track if this was a loss
        daily_reentry_count[ticker] = daily_reentry_count.get(ticker, 0) + 1
        cooldown_type = "loss" if pnl < 0 else "win"
        log_message(f"   📝 Cooldown activated for {ticker} ({cooldown_type}, re-entries today: {daily_reentry_count[ticker]})")
        # ===== END COOLDOWN TRACKING =====
        
        # Send webhook notification
        webhook_data = {
            'action': 'SELL',
            'ticker': ticker,
            'price': exit_price,
            'shares': pos['shares'],
            'entry_price': pos['entry_price'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason.replace('_', ' ').title()
        }
        send_webhook(webhook_data)
        
        emoji = "🟢" if pnl > 0 else "🔴"
        shares_str = f"{pos['shares']:.4f}" if pos['shares'] < 1 else f"{pos['shares']:.2f}"
        print_alert(
            f"SELL {ticker} @ ${exit_price:.2f}\n"
            f"     Reason: {reason.replace('_', ' ').title()}\n"
            f"     Shares: {shares_str}\n"
            f"     Entry: ${pos['entry_price']:.2f}\n"
            f"     P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
            f"     Capital: ${capital:,.2f}",
            emoji
        )
        
        # Delete position from memory and database
        del positions[ticker]
        delete_position_from_db(ticker)

def calculate_unrealized_pnl(current_prices):
    """Calculate unrealized P&L for open positions."""
    total = 0.0
    for ticker, pos in positions.items():
        price = current_prices.get(ticker, pos['entry_price'])
        total += pos['shares'] * (price - pos['entry_price'])
    return total

def publish_bot_status(current_prices, breakers=None):
    """Publish bot status to Redis for dashboard truthfulness."""
    try:
        r = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            decode_responses=True,
        )

        realized_pnl = sum(t.get('pnl', 0) for t in trades if t.get('action') == 'SELL')
        unrealized_pnl = calculate_unrealized_pnl(current_prices)
        paper_equity = capital + sum(
            pos['shares'] * current_prices.get(t, pos['entry_price'])
            for t, pos in positions.items()
        )

        have_broker_equity = broker_equity is not None and float(broker_equity) > 0
        have_broker_cash = broker_cash is not None and float(broker_cash) >= 0

        # IMPORTANT: In paper mode, the bot's 'equity'/'cash' should reflect paper accounting.
        # Broker balances (often ~10k in practice accounts) are informational only.
        if PAPER_TRADING:
            equity_source = 'paper'
            cash_source = 'paper'
            display_equity = float(paper_equity)
            display_cash = float(capital)
        else:
            equity_source = 'broker' if have_broker_equity else 'paper'
            cash_source = 'broker' if have_broker_cash else 'paper'
            display_equity = float(broker_equity) if have_broker_equity else float(paper_equity)
            display_cash = float(broker_cash) if have_broker_cash else float(capital)

        status = {
            'timestamp': datetime.now().isoformat(),
            'mode': 'paper' if PAPER_TRADING else 'live',
            'equity_source': equity_source,
            'cash_source': cash_source,
            'cash': round(display_cash, 4),
            'equity': round(display_equity, 4),
            'paper_cash': round(float(capital), 4),
            'paper_equity': round(float(paper_equity), 4),
            'broker_cash': round(float(broker_cash), 4) if have_broker_cash else None,
            'broker_equity': round(float(broker_equity), 4) if have_broker_equity else None,
            'daily_start_equity': round(daily_start_equity, 4),
            'realized_pnl': round(realized_pnl, 4),
            'unrealized_pnl': round(unrealized_pnl, 4),
            'open_positions': len(positions),
            'breakers': breakers or {}
        }

        payload = json.dumps(status)
        # Legacy key (older dashboards) + v2 key (preferred)
        r.setex('bot_status', 120, payload)
        r.setex('bot_status_v2', 120, payload)
    except Exception:
        # Silent fail to avoid disrupting trading
        pass

def scan_and_trade(historical_data, current_prices, quote_map, available_capital):
    """Scan for opportunities and enter trades"""
    global capital, positions, consecutive_losses, market_regime_ok, starting_equity
    global trade_block_stats
    
    # FEATURE #2: Time-of-Day Trading Window Check
    is_valid_time, time_reason = is_within_trading_window()
    if not is_valid_time:
        log_message(f"\n🚫 TRADING WINDOW BLOCKED: {time_reason}", False)
        return
    
    # CIRCUIT BREAKER 1: Check consecutive losses
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        log_message(f"\n🚨 CIRCUIT BREAKER: {consecutive_losses} consecutive losses", False)
        log_message(f"   Trading paused - manual review required", False)
        send_error_alert("Consecutive Losses", f"{consecutive_losses} losing trades in a row", critical=True)
        return
    
    # CIRCUIT BREAKER 2: Check daily portfolio loss (USD + percent)
    current_equity = capital + sum(pos['shares'] * current_prices.get(t, pos['entry_price']) 
                                   for t, pos in positions.items())
    daily_loss_usd = current_equity - daily_start_equity
    daily_loss_pct = (daily_loss_usd / daily_start_equity) if daily_start_equity > 0 else 0
    if daily_loss_usd <= -MAX_DAILY_LOSS_USD:
        log_message(f"\n🚨 CIRCUIT BREAKER: Daily loss ${daily_loss_usd:,.2f} <= -${MAX_DAILY_LOSS_USD:,.2f}", False)
        log_message(f"   Trading paused for today", False)
        send_error_alert("Daily Loss Limit", f"Portfolio down ${daily_loss_usd:,.2f}", critical=True)
        return
    if daily_loss_pct <= -MAX_DAILY_LOSS_PCT:
        log_message(f"\n🚨 CIRCUIT BREAKER: Daily loss {daily_loss_pct*100:.1f}% >= {MAX_DAILY_LOSS_PCT*100:.0f}%", False)
        log_message(f"   Trading paused for today", False)
        send_error_alert("Daily Loss Limit", f"Portfolio down {daily_loss_pct*100:.1f}%", critical=True)
        return
    
    # CIRCUIT BREAKER 3: Check market regime
    if not market_regime_ok:
        log_message(f"\n⚠️ Market regime unfavorable - skipping new trades", False)
        return
    
    # Don't trade if we're at max positions
    if len(positions) >= MAX_POSITIONS:
        return
    
    # Filter for affordable stocks first
    affordable_prices = filter_affordable_stocks(current_prices, available_capital)
    
    if not affordable_prices:
        log_message("   ⚠️ No affordable stocks to scan", False)
        return
    
    # Calculate scores for all stocks with detailed logging
    scores = {}
    candidates_checked = 0
    detailed_results = {}  # Store full details for all stocks
    
    log_message(f"\n   🔍 Scanning {len(affordable_prices)} stocks:", False)
    
    # First scan affordable stocks
    for ticker, df in historical_data.items():
        if ticker in positions:
            continue
        if ticker not in affordable_prices:  # Use affordable_prices instead of current_prices
            continue
        
        candidates_checked += 1
        current_price = affordable_prices[ticker]
        
        # Update dataframe with current price for today's action
        momentum, volume_ratio, volatility = calculate_momentum_score(df, current_price)
        
        # Track detailed results for every stock
        stock_info = {
            'price': current_price,
            'momentum': momentum,
            'volume_ratio': volume_ratio,
            'volatility': volatility,
            'status': '',
            'reason': ''
        }
        
        # Check each filter and log the specific failure
        if momentum is None:
            stock_info['status'] = '❌'
            stock_info['reason'] = 'No data'
        elif momentum <= 0:
            stock_info['status'] = '❌'
            stock_info['reason'] = f'Momentum {momentum:.4f} <= 0'
        elif volume_ratio < MIN_VOLUME_RATIO:
            stock_info['status'] = '❌'
            stock_info['reason'] = f'Volume {volume_ratio:.1%} < {MIN_VOLUME_RATIO:.1%}'
        elif volatility >= MAX_VOLATILITY:
            stock_info['status'] = '❌'
            stock_info['reason'] = f'Volatility {volatility:.2%} >= {MAX_VOLATILITY:.2%}'
        else:
            stock_info['status'] = '✅'
            stock_info['reason'] = f'PASS (Score: {momentum:.4f})'
            scores[ticker] = momentum
        
        detailed_results[ticker] = stock_info
    
    # Display detailed results for ALL stocks
    for ticker in sorted(detailed_results.keys()):
        info = detailed_results[ticker]
        log_message(f"      {info['status']} {ticker}: ${info['price']:.2f} - {info['reason']}", False)
    
    # Summary
    if scores:
        log_message(f"\n   ✅ Found {len(scores)} qualifying stocks", False)
    else:
        log_message(f"\n   ⚠️  No stocks met all criteria", False)
    
    if not scores:
        return
    
    # Get top opportunities
    top_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    available_slots = MAX_POSITIONS - len(positions)
    
    for ticker, score in top_stocks[:available_slots]:
        current_price = current_prices.get(ticker)
        if not current_price:
            log_message(f"   🚫 {ticker}: Missing current price", False)
            continue
        
        # ===== RE-ENTRY COOLDOWN CHECKS =====
        
        # Check 1: Time-based cooldown (stricter after losses)
        if ticker in last_sell_times:
            time_since_sell = (datetime.now() - last_sell_times[ticker]).total_seconds() / 60
            required_cooldown = COOLDOWN_AFTER_LOSS_MINUTES if last_sell_was_loss.get(ticker, False) else COOLDOWN_MINUTES
            if time_since_sell < required_cooldown:
                log_message(f"   🚫 {ticker}: Cooldown active ({time_since_sell:.1f} min < {required_cooldown} min)", False)
                continue
        
        # Check 2: Price change requirement (1%)
        if ticker in last_sell_prices:
            price_change_pct = abs(current_price - last_sell_prices[ticker]) / last_sell_prices[ticker]
            if price_change_pct < MIN_PRICE_CHANGE_PCT:
                log_message(f"   🚫 {ticker}: Price unchanged ({price_change_pct:.2%} < {MIN_PRICE_CHANGE_PCT:.1%})", False)
                continue
        
        # Check 2b: Higher momentum threshold for re-entry (especially after loss)
        if ticker in last_sell_times:
            if score < MIN_MOMENTUM_REENTRY:
                log_message(f"   🚫 {ticker}: Momentum too low for re-entry ({score:.4f} < {MIN_MOMENTUM_REENTRY})", False)
                continue
        
        # Check 3: Daily re-entry limit (optional)
        daily_count = daily_reentry_count.get(ticker, 0)
        if MAX_DAILY_REENTRIES > 0 and daily_count >= MAX_DAILY_REENTRIES:
            log_message(f"   🚫 {ticker}: Max re-entries reached ({daily_count}/{MAX_DAILY_REENTRIES} today)", False)
            continue
        
        # ===== END COOLDOWN CHECKS =====
        
        # FEATURE #3: Earnings Blackout Check
        is_blocked, earnings_reason = check_earnings_blackout(ticker)
        if is_blocked:
            log_message(f"   🚫 {ticker}: {earnings_reason}", False)
            continue

        # Quote availability + staleness gate
        quote_data = quote_map.get(ticker)
        if not quote_data:
            log_message(f"   🚫 {ticker}: Missing quote data", False)
            trade_block_stats['entry_block_missing_quote'] += 1
            continue

        is_stale, age_seconds = is_quote_stale(quote_data)
        if is_stale:
            age_msg = f"{age_seconds:.0f}s" if age_seconds is not None else "unknown age"
            log_message(f"   🚫 {ticker}: Stale quote ({age_msg})", False)
            trade_block_stats['entry_block_stale_quote'] += 1
            continue

        # Liquidity/spread gate
        is_liquid, liq_reason = check_liquidity(ticker, quote_data)
        if not is_liquid:
            log_message(f"   🚫 {ticker}: {liq_reason}", False)
            continue

        # Risk-based position sizing (primary limiter)
        stop_loss_preview = current_price * (1 - STOP_LOSS_PCT)
        risk_per_share = current_price - stop_loss_preview
        if risk_per_share <= 0:
            log_message(f"   🚫 {ticker}: Invalid risk per share", False)
            continue

        shares_by_risk = RISK_PER_TRADE_USD / risk_per_share
        max_position_value = capital * BASE_POSITION_SIZE_PCT
        shares_by_cap = max_position_value / current_price
        shares = min(shares_by_risk, shares_by_cap)

        if FRACTIONAL_SHARES_ENABLED:
            cost = shares * current_price
        else:
            shares = int(shares)
            cost = shares * current_price + COMMISSION

        if shares <= 0 or cost <= 0:
            log_message(f"   🚫 {ticker}: Position size too small after risk sizing", False)
            continue
        
        # FEATURE #1: CRITICAL SAFETY CHECK - Validate position size before order
        is_valid, adjusted_max_value = validate_position_size(ticker, shares, current_price, capital)
        
        if not is_valid:
            # Position size exceeds safety limit - recalculate with adjusted size
            log_message(f"   📉 Adjusting {ticker} position to safety limit: ${adjusted_max_value:.2f}")
            
            if FRACTIONAL_SHARES_ENABLED:
                shares = adjusted_max_value / current_price
                cost = shares * current_price
            else:
                shares = int(adjusted_max_value / current_price)
                cost = shares * current_price + COMMISSION
            
            # Validate again after adjustment
            is_valid_retry, _ = validate_position_size(ticker, shares, current_price, capital)
            if not is_valid_retry:
                log_message(f"   ❌ {ticker}: Still exceeds limit after adjustment - SKIPPING")
                continue
        
        # Ensure we have at least a minimum position
        if cost >= 1.0 and cost <= capital * 0.85:
            # Only use 85% of capital to leave buffer

            # PAPER TRADING: Simulate fill, LIVE TRADING: Place actual order
            if PAPER_TRADING:
                filled_shares, fill_price, fill_note = simulate_paper_fill(ticker, "BUY", shares, quote_data)
                if not fill_price:
                    log_message(f"   🚫 {ticker}: Paper fill skipped ({fill_note})", False)
                    continue
                shares = filled_shares
                cost = shares * fill_price + COMMISSION
                log_message(f"   🧪 Paper trade: {fill_note} at ${fill_price:.2f}")
            else:
                # LIVE MODE - Place actual limit order (NOT IMPLEMENTED YET)
                log_message(f"   ⚠️ LIVE ORDER EXECUTION NOT YET IMPLEMENTED")
                log_message(f"   Set PAPER_TRADING=True to simulate")
                continue

            capital -= cost

            # Dynamic take profit based on stock price
            take_profit_pct = HIGH_PRICE_TAKE_PROFIT_PCT if fill_price > HIGH_PRICE_THRESHOLD else TAKE_PROFIT_PCT

            positions[ticker] = {
                'shares': shares,
                'entry_price': fill_price,
                'entry_date': datetime.now(),
                'entry_time': datetime.now(),
                'highest_price': fill_price,
                'stop_loss': fill_price * (1 - STOP_LOSS_PCT),
                'take_profit': fill_price * (1 + take_profit_pct),
                'trailing_stop': fill_price * (1 - TRAILING_STOP_PCT),
                'current_price': fill_price,
                'unrealized_pnl': 0,
                'unrealized_pnl_pct': 0
            }

            # Save position to database
            save_position_to_db(ticker, positions[ticker])

            # Log trade to history
            log_trade_to_db(
                ticker=ticker,
                action='BUY',
                shares=shares,
                price=fill_price,
                capital_before=capital + cost,  # Capital before this buy
                total_positions=len(positions),
                notes=f"Momentum score: {score:.4f}"
            )

            trade = {
                'time': datetime.now().strftime('%I:%M:%S %p'),
                'action': 'BUY',
                'ticker': ticker,
                'price': fill_price,
                'shares': shares,  # Can be fractional (e.g., 0.164 shares)
                'cost': cost,
                'momentum': score
            }
            trades.append(trade)
            
            # Send webhook notification
            webhook_data = {
                'action': 'BUY',
                'ticker': ticker,
                'price': fill_price,
                'shares': shares,
                'momentum': score
            }
            send_webhook(webhook_data)
            
            shares_str = f"{shares:.4f}" if shares < 1 else f"{shares:.2f}"
            print_alert(
                f"BUY {ticker} @ ${fill_price:.2f}\n"
                f"     Momentum Score: {score:.4f}\n"
                f"     Shares: {shares_str}\n"
                f"     Cost: ${cost:,.2f}\n"
                f"     Stop Loss: ${positions[ticker]['stop_loss']:.2f} (-{STOP_LOSS_PCT*100:.1f}%)\n"
                f"     Take Profit: ${positions[ticker]['take_profit']:.2f} (+{take_profit_pct*100:.1f}%)\n"
                f"     Capital Remaining: ${capital:,.2f}",
                "🟢"
            )

# Main loop
print_header("🔄 STARTING LIVE MONITORING")
log_message("\n⏰ Press Ctrl+C to stop\n")

try:
    while True:  # Run continuously until Ctrl+C, remote stop, drawdown limit, or market close
        checks += 1
        now = datetime.now()
        current_time = now.strftime('%I:%M:%S %p')
        elapsed_minutes = int((now - start_time).total_seconds() / 60)

        # Optional timed run (useful for controlled paper tests)
        if MAX_RUNTIME_MINUTES and MAX_RUNTIME_MINUTES > 0 and elapsed_minutes >= MAX_RUNTIME_MINUTES:
            log_message(f"\n⏹️  MAX_RUNTIME_MINUTES reached ({MAX_RUNTIME_MINUTES:.0f} min) - stopping")
            break

        # Market-closed guard (holiday/weekend/outside regular session): do not scan/enter.
        market_now = get_now_eastern()
        is_open_now, market_reason, next_open_dt = get_us_market_state(market_now)
        if (not is_open_now) and (not Path(REMOTE_STOP_FILE).exists()):
            breakers_status = {
                'market_open': False,
                'market_reason': market_reason,
                'next_open': next_open_dt.isoformat() if next_open_dt else None,
            }
            publish_bot_status(last_known_prices or {}, breakers_status)

            idle_seconds = int(os.getenv('MARKET_IDLE_POLL_SECONDS', '60'))
            # Log about once per ~10 minutes (regardless of idle interval)
            log_every = max(int(600 / max(idle_seconds, 1)), 1)
            if checks % log_every == 0:
                next_open_str = next_open_dt.strftime('%a %m/%d %I:%M %p ET') if next_open_dt else 'unknown'
                log_message(f"\n⏸️  MARKET CLOSED: {market_reason} | Next open: {next_open_str} | Idling {idle_seconds}s")

            time_sleep.sleep(idle_seconds)
            continue
        
        # API Token Auto-Refresh (every 25 minutes to prevent 30-min expiry)
        minutes_since_refresh = (now - token_refresh_time).total_seconds() / 60
        if minutes_since_refresh >= TOKEN_REFRESH_INTERVAL_MINUTES:
            try:
                log_message(f"   🔄 Refreshing Questrade API token (last refresh: {minutes_since_refresh:.1f} min ago)...")
                questrade.refresh_access_token()
                token_refresh_time = now
                log_message(f"   ✅ Token refreshed successfully")
            except Exception as e:
                log_message(f"   ⚠️ Token refresh failed: {str(e)}")
                log_message(f"   Will retry on next cycle")
        
        # Check for remote stop flag
        if Path(REMOTE_STOP_FILE).exists():
            log_message(f"\n🛑 REMOTE STOP DETECTED")
            log_message(f"   Found: {REMOTE_STOP_FILE}")
            log_message(f"   Stopping trading gracefully...")
            
            # Close all positions before stopping
            if positions:
                log_message(f"\n📦 Closing {len(positions)} open positions...")
                current_prices, quote_map = get_current_prices_questrade(list(positions.keys()))
                for ticker in list(positions.keys()):
                    if ticker in current_prices:
                        check_positions(current_prices, quote_map)  # Will close positions
            
            # Delete the stop file
            Path(REMOTE_STOP_FILE).unlink()
            log_message(f"   ✅ Stop file removed")
            break
        
        # (Market close is handled by the market-closed guard above)
        
        log_message(f"\n{'─' * 80}")
        log_message(f"🔍 Check #{checks} at {current_time} (Elapsed: {elapsed_minutes} min)")
        
        # Check market regime (VIX/SPY) - only every 10 checks to reduce overhead
        if checks % 10 == 0:
            market_regime_ok, regime_msg = check_market_regime()
            if not market_regime_ok:
                log_message(f"   ⚠️ Market regime: {regime_msg}")
        
        # Get current prices from Questrade
        log_message("   📊 Fetching live prices from Questrade...")
        prices_from_cache = False
        current_prices, quote_map = get_current_prices_questrade(TRADING_UNIVERSE)
        
        # Fallback to last known prices if API fails
        if not current_prices or len(current_prices) == 0:
            log_message(f"   ⚠️ API returned no prices - using last known prices")
            if last_known_prices:
                current_prices = last_known_prices.copy()
                quote_map = last_known_quotes.copy()
                prices_from_cache = True
                log_message(f"   ✓ Using {len(current_prices)} cached prices")
            else:
                log_message(f"   ❌ No cached prices available - skipping this cycle")
                time_sleep.sleep(CHECK_INTERVAL_SECONDS)
                continue
        else:
            # Update cache with successful price fetch
            last_known_prices = current_prices.copy()
            last_known_quotes = quote_map.copy()
            log_message(f"   ✓ Got prices for {len(current_prices)} stocks")
            
            # Write prices to Redis for dashboard (in-memory cache)
            try:
                r = redis.Redis(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=int(os.getenv('REDIS_PORT', '6379')),
                    decode_responses=True,
                )
                r.setex('live_prices', 60, json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'source': 'redis',
                    'prices': current_prices
                }))
            except Exception as e:
                # Silent fail - don't disrupt trading if Redis unavailable
                pass
        
        # Check existing positions for exits
        if positions:
            check_positions(current_prices, quote_map)
            # Update position P&L in database (only if shares > 0)
            for ticker, pos in positions.items():
                if ticker in current_prices and pos['shares'] > 0:
                    pos['current_price'] = current_prices[ticker]
                    pos['unrealized_pnl'] = pos['shares'] * (current_prices[ticker] - pos['entry_price']) - COMMISSION
                    pos['unrealized_pnl_pct'] = ((current_prices[ticker] - pos['entry_price']) / pos['entry_price']) * 100
                    save_position_to_db(ticker, pos)
        
        # Calculate current equity and drawdown
        current_equity = capital
        for ticker, pos in positions.items():
            if ticker in current_prices:
                current_equity += pos['shares'] * current_prices[ticker]
        
        drawdown_pct = ((current_equity - starting_equity) / starting_equity) * 100
        
        # Track maximum drawdown reached
        if drawdown_pct < max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
        
        # DRAWDOWN AUTO-STOP: Check for 20% loss
        if drawdown_pct <= -MAX_DRAWDOWN_PCT * 100:
            error_msg = f"Drawdown limit reached: {drawdown_pct:.2f}% (max: -{MAX_DRAWDOWN_PCT*100:.0f}%)"
            log_message(f"\n🚨 AUTO-STOP TRIGGERED: {error_msg}")
            send_error_alert("Drawdown Limit Reached", error_msg, critical=True)
            
            # Close all positions
            if positions:
                log_message(f"\n📦 Closing all {len(positions)} positions...")
                for ticker in list(positions.keys()):
                    if ticker in current_prices:
                        # Force close at market price
                        check_positions(current_prices, quote_map)
            
            log_message(f"   🛑 Trading stopped to prevent further losses")
            break
        
        # Fresh-quote requirement status (especially for exits): detect stale/missing quotes for open positions.
        stale_position_tickers = []
        if positions:
            for t in positions.keys():
                q = quote_map.get(t) if quote_map else None
                is_stale, _age = is_quote_stale(q)
                if is_stale:
                    stale_position_tickers.append(t)

        # Scan for new opportunities (pass capital for affordability check)
        data_feed_reason = None
        if prices_from_cache:
            err = last_quote_fetch_error or "Unknown quote fetch error"
            data_feed_reason = f"Questrade returned no prices; using cached prices ({err})"
            log_message(f"   🚫 Entries paused: {data_feed_reason} (feed degraded)")
            trade_block_stats['entries_paused_cache_cycles'] += 1
        elif stale_position_tickers:
            sample = ", ".join(stale_position_tickers[:6])
            suffix = "" if len(stale_position_tickers) <= 6 else f" +{len(stale_position_tickers) - 6} more"
            data_feed_reason = f"Stale/missing quotes for positions: {sample}{suffix}"
            log_message(f"   🚫 Entries paused: {data_feed_reason} (cannot safely exit positions)")
            trade_block_stats['entries_paused_stale_positions_cycles'] += 1
        else:
            scan_and_trade(historical_data, current_prices, quote_map, capital)
        
        # Current status (recalculate equity after potential trades)
        current_equity = capital
        for ticker, pos in positions.items():
            if ticker in current_prices:
                current_equity += pos['shares'] * current_prices[ticker]
        
        pnl = current_equity - starting_equity
        pnl_pct = (pnl / starting_equity) * 100

        daily_loss_usd = current_equity - daily_start_equity

        breakers_status = {
            'daily_loss_limit': daily_loss_usd <= -MAX_DAILY_LOSS_USD,
            'consecutive_losses': consecutive_losses >= MAX_CONSECUTIVE_LOSSES,
            'market_regime_ok': market_regime_ok,
            'prices_from_cache': prices_from_cache,
            'data_feed_ok': (not prices_from_cache) and (len(stale_position_tickers) == 0),
            'data_feed_reason': data_feed_reason,
            'stale_position_quote_count': len(stale_position_tickers),
            'stale_position_quote_tickers': stale_position_tickers[:10],
            'trade_block_stats': dict(trade_block_stats),
        }
        publish_bot_status(current_prices, breakers_status)
        
        log_message(f"\n   \ud83d\udcc8 Current Status:")
        log_message(f"      Equity: ${current_equity:,.2f}")
        log_message(f"      P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
        log_message(f"      Cash: ${capital:,.2f}")
        log_message(f"      Positions: {len(positions)}/{MAX_POSITIONS}")
        log_message(f"      Drawdown: {drawdown_pct:+.2f}% (limit: -{MAX_DRAWDOWN_PCT*100:.0f}%)")
        
        if positions:
            log_message(f"\n   🔹 Open Positions:")
            for ticker, pos in positions.items():
                if ticker in current_prices:
                    current_price = current_prices[ticker]
                    unrealized_pnl = (current_price - pos['entry_price']) * pos['shares']
                    unrealized_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                    log_message(f"      {ticker}: ${current_price:.2f} ({unrealized_pct:+.2f}%) - {pos['shares']} shares")
        
        # Wait for next check
        time_sleep.sleep(CHECK_INTERVAL_SECONDS)
        
except KeyboardInterrupt:
    log_message("\n\n⚠️  Test stopped by user")

# Final summary
print_header("📊 FINAL RESULTS")

end_time = datetime.now()
duration = (end_time - start_time).total_seconds() / 60

# Get final prices and calculate final equity
final_prices, _ = get_current_prices_questrade(TRADING_UNIVERSE)
final_equity = capital
for ticker, pos in positions.items():
    if ticker in final_prices:
        final_equity += pos['shares'] * final_prices[ticker]

log_message(f"\n⏰ End Time: {end_time.strftime('%I:%M:%S %p EST')}")
log_message(f"⏱️  Duration: {duration:.1f} minutes")
log_message(f"🔍 Checks Performed: {checks}")

log_message(f"\n💰 PERFORMANCE:")
log_message(f"   Starting Capital: ${starting_equity:,.2f}")
log_message(f"   Ending Equity:    ${final_equity:,.2f}")
log_message(f"   Net P&L:          ${final_equity - starting_equity:+,.2f}")
log_message(f"   Return:           {((final_equity - starting_equity) / starting_equity * 100):+.2f}%")
log_message(f"   Max Drawdown:     {max_drawdown_pct:+.2f}%")

log_message(f"\n🛰️  QUOTE / FEED SAFETY (blocked counts):")
log_message(f"   QUOTE_STALE_SECONDS: {QUOTE_STALE_SECONDS}s")
log_message(f"   Entries paused (cached prices cycles): {trade_block_stats.get('entries_paused_cache_cycles', 0)}")
log_message(f"   Entries paused (stale quotes in positions cycles): {trade_block_stats.get('entries_paused_stale_positions_cycles', 0)}")
log_message(f"   Entry blocks (missing quote): {trade_block_stats.get('entry_block_missing_quote', 0)}")
log_message(f"   Entry blocks (stale quote): {trade_block_stats.get('entry_block_stale_quote', 0)}")
log_message(f"   Exit blocks (stale/missing quote): {trade_block_stats.get('exit_block_stale_or_missing_quote', 0)}")

if trades:
    log_message(f"\n📋 TRADES EXECUTED: {len(trades)}")
    buys = [t for t in trades if t['action'] == 'BUY']
    sells = [t for t in trades if t['action'] == 'SELL']
    
    log_message(f"   📊 Summary:")
    log_message(f"      Total Trades:  {len(trades)}")
    log_message(f"      Buys:          {len(buys)}")
    log_message(f"      Sells:         {len(sells)}")
    
    # Calculate win rate from sells
    if sells:
        winning_trades = len([t for t in sells if t['pnl'] > 0])
        win_rate = (winning_trades / len(sells)) * 100
        log_message(f"      Win Rate:      {win_rate:.1f}% ({winning_trades}/{len(sells)})")
        
        total_pnl = sum([t['pnl'] for t in sells])
        avg_pnl = total_pnl / len(sells)
        log_message(f"      Total Realized: ${total_pnl:+,.2f}")
        log_message(f"      Avg P&L/Trade:  ${avg_pnl:+,.2f}")
    
    log_message(f"\n   🟢 BUYS ({len(buys)}):")
    if buys:
        for trade in buys:
            shares_str = f"{trade['shares']:.4f}" if trade['shares'] < 1 else f"{trade['shares']:.2f}"
            log_message(f"      {trade['time']} - {trade['ticker']}: {shares_str} shares @ ${trade['price']:.2f} = ${trade['cost']:.2f}")
    else:
        log_message(f"      None")
    
    if sells:
        log_message(f"\n   🔴 SELLS ({len(sells)}):")
        for trade in sells:
            emoji = "🟢" if trade['pnl'] > 0 else "🔴"
            shares_str = f"{trade['shares']:.4f}" if trade['shares'] < 1 else f"{trade['shares']:.2f}"
            log_message(f"      {emoji} {trade['time']} - {trade['ticker']}: {shares_str} shares @ ${trade['exit_price']:.2f} | P&L: ${trade['pnl']:+,.2f} ({trade['pnl_pct']:+.2f}%) | {trade['reason'].replace('_', ' ').title()}")
else:
    log_message(f"\n📋 TRADES EXECUTED: 0")
    log_message(f"   ℹ️  No trades triggered during test period")

if positions:
    log_message(f"\n🔹 OPEN POSITIONS (EOD): {len(positions)}")
    total_unrealized = 0
    for ticker, pos in positions.items():
        if ticker in final_prices:
            current_price = final_prices[ticker]
            unrealized_pnl = (current_price - pos['entry_price']) * pos['shares']
            unrealized_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
            total_unrealized += unrealized_pnl
            shares_str = f"{pos['shares']:.4f}" if pos['shares'] < 1 else f"{pos['shares']:.2f}"
            log_message(f"      {ticker}: {shares_str} shares @ ${pos['entry_price']:.2f} → ${current_price:.2f} | Unrealized: ${unrealized_pnl:+,.2f} ({unrealized_pct:+.2f}%)")
    log_message(f"   Total Unrealized P&L: ${total_unrealized:+,.2f}")
else:
    log_message(f"\n🔹 OPEN POSITIONS (EOD): 0")

# Day overview
log_message(f"\n📈 DAY OVERVIEW:")
log_message(f"   Positions at Open: {starting_positions_count}")
log_message(f"   New Positions:     {len([t for t in trades if t['action'] == 'BUY']) if trades else 0}")
log_message(f"   Closed Positions:  {len([t for t in trades if t['action'] == 'SELL']) if trades else 0}")
log_message(f"   Positions at Close: {len(positions)}")

# Machine-readable summary for n8n/webhook parsing
buys_count = len([t for t in trades if t['action'] == 'BUY']) if trades else 0
sells_count = len([t for t in trades if t['action'] == 'SELL']) if trades else 0
total_trades = len(trades) if trades else 0
net_pnl = final_equity - starting_equity
return_pct = ((final_equity - starting_equity) / starting_equity * 100) if starting_equity > 0 else 0

log_message(f"\n{'='*80}")
log_message("SUMMARY_DATA_START")
log_message(f"DATE={datetime.now().strftime('%m/%d/%Y')}")
log_message(f"START_TIME={start_time.strftime('%I:%M %p')}")
log_message(f"END_TIME={end_time.strftime('%I:%M %p')}")
log_message(f"STARTING_EQUITY={starting_equity:.2f}")
log_message(f"ENDING_EQUITY={final_equity:.2f}")
log_message(f"NET_PNL={net_pnl:+.2f}")
log_message(f"RETURN_PCT={return_pct:+.2f}")
log_message(f"TOTAL_TRADES={total_trades}")
log_message(f"BUYS={buys_count}")
log_message(f"SELLS={sells_count}")
log_message(f"OPEN_POSITIONS={len(positions)}")
log_message(f"MAX_DRAWDOWN={max_drawdown_pct:.2f}")
log_message("SUMMARY_DATA_END")
log_message(f"{'='*80}")

print_header("✅ Test Complete!")
log_message(f"\n📝 Full log saved to: {log_file}\n")
