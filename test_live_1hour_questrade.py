"""
Live Paper Trading using Questrade
Runs continuously during market hours with real-time data
Creates detailed trade log in trades_log_TIMESTAMP.txt
Press Ctrl+C to stop
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
from glob import glob
from pathlib import Path
import requests
from dotenv import load_dotenv

# Import existing modules
from quant_agent.questrade_loader import QuestradeAPI
from quant_agent.config_loader import ConfigLoader
import psycopg2
from psycopg2.extras import RealDictCursor

# PAPER TRADING SAFETY FLAG
PAPER_TRADING = True  # Set to False ONLY when ready for live money

# FRACTIONAL SHARES SUPPORT
FRACTIONAL_SHARES_ENABLED = True  # Questrade supports fractional shares (US stocks only)

# Configuration
INITIAL_CAPITAL = 100000  # Fallback only - will be replaced with live balance
MAX_POSITIONS = 3
BASE_POSITION_SIZE_PCT = 0.25
COMMISSION = 0.0  # Fractional shares are commission-free on Questrade!

# Risk Controls
STOP_LOSS_PCT = 0.15
TAKE_PROFIT_PCT = 0.40
TRAILING_STOP_PCT = 0.12
MIN_VOLUME_RATIO = 0.3  # Relaxed for midday trading
MAX_VOLATILITY = 0.06
MAX_DRAWDOWN_PCT = 0.20  # 20% max drawdown auto-stop
MAX_DAILY_LOSS_PCT = 0.08  # 8% max daily portfolio loss
MAX_CONSECUTIVE_LOSSES = 3  # Pause after 3 losing trades

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

# n8n Webhook Configuration
N8N_WEBHOOK_ENABLED = True
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/trade-alerts"

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

# Trading mode indicator
trading_mode = "🧪 PAPER TRADING MODE" if PAPER_TRADING else "💰 LIVE TRADING MODE"

print_header(f"🔴 LIVE TRADING - QUESTRADE - {trading_mode}")

# Initialize
start_time = datetime.now()
starting_equity = INITIAL_CAPITAL  # Will be updated with live balance
daily_start_equity = INITIAL_CAPITAL  # Track for daily loss limiter
consecutive_losses = 0  # Track losing streak
total_closed_trades = 0  # For loss tracking
market_regime_ok = True  # Market condition flag

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
    log_message("✅ Connected to Questrade successfully!")
    log_message(f"   Server: {questrade.api_server}")
    log_message(f"   Mode: {questrade.server_type}")
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
    
    # Use live equity as starting capital
    capital = live_equity
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
    
    # PRE-FLIGHT WARNING: Stock affordability with small capital
    max_affordable_price = capital * MAX_PRICE_PER_SHARE_PCT
    log_message(f"\n⚠️  CAPITAL CONSTRAINTS:")
    log_message(f"   📊 Total Capital: ${capital:.2f}")
    log_message(f"   💰 Max Position Size: ${capital / MAX_POSITIONS:.2f} each")
    log_message(f"   📈 Max Affordable Share Price: ${max_affordable_price:.2f}")
    log_message(f"   ⚠️  Warning: Only stocks under ${max_affordable_price:.2f} can be traded")
    log_message(f"   💸 Commission Impact: ${COMMISSION:.2f} per trade = {(COMMISSION / (capital / MAX_POSITIONS)) * 100:.1f}% of position")
    
except Exception as e:
    error_msg = f"Failed to fetch account balance: {str(e)}"
    log_message(f"❌ {error_msg}")
    log_message(f"   Using fallback capital: ${INITIAL_CAPITAL:,}")
    send_error_alert("Balance Fetch Failed", error_msg, critical=False)
    capital = INITIAL_CAPITAL
    starting_equity = INITIAL_CAPITAL

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
    data_age_days = (datetime.now() - most_recent_date).days
    
    if data_age_days > 1:
        error_msg = f"Historical data is {data_age_days} days old (last: {most_recent_date.date()})"
        log_message(f"\n🚨 SAFETY CHECK FAILED: {error_msg}")
        log_message("   Run download_historical_data.py to update data before trading")
        send_error_alert("Stale Data Detected", error_msg, critical=True)
        exit(1)
    
    log_message(f"   ✅ Data freshness check passed (last update: {most_recent_date.date()})")
except Exception as e:
    log_message(f"⚠️ Could not verify data freshness: {str(e)}")

# Load existing positions from database
log_message("\n💾 Loading positions from database...")
positions = load_positions_from_db()
trades = []
checks = 0

if positions:
    log_message(f"   📁 Found {len(positions)} open positions:")
    for ticker, pos in positions.items():
        pnl_pct = pos.get('unrealized_pnl_pct', 0)
        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
        shares_str = f"{pos['shares']:.4f}" if pos['shares'] < 1 else f"{pos['shares']:.2f}"
        log_message(f"      {pnl_emoji} {ticker}: {shares_str} shares @ ${pos['entry_price']:.2f} ({pnl_pct:+.1f}%)")
    
    # POSITION RECONCILIATION: Compare DB vs Broker
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
    """Get current prices from Questrade"""
    prices = {}
    errors = []
    
    try:
        # Get symbol IDs first
        symbol_ids = {}
        for ticker in tickers:
            try:
                # Search for symbol ID
                symbol_id = questrade.search_symbols(ticker)
                if symbol_id:
                    # Found the symbol
                    symbol_ids[ticker] = symbol_id
                else:
                    # Symbol not found, log it
                    errors.append(f"{ticker}: Not found on Questrade")
            except Exception as e:
                error_msg = f"{ticker}: Search error - {str(e)[:50]}"
                errors.append(error_msg)
                # Alert on timeout or connection errors
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    send_error_alert("API Search Error", error_msg, critical=False)
        
        # Log search results
        if len(symbol_ids) == 0:
            error_msg = "No symbols found on Questrade - check API access"
            log_message(f"   ⚠️  {error_msg}", False)
            if errors[:3]:  # Show first 3 errors
                for err in errors[:3]:
                    log_message(f"      - {err}", False)
            send_error_alert("Symbol Lookup Failed", f"{error_msg}. Errors: {len(errors)}", critical=True)
            return prices
        
        # Get quotes for all symbols
        if symbol_ids:
            try:
                symbol_id_list = list(symbol_ids.values())
                quotes = questrade.get_quotes(symbol_id_list)
                
                # Map back to tickers
                id_to_ticker = {v: k for k, v in symbol_ids.items()}
                for quote in quotes:
                    ticker = id_to_ticker.get(quote['symbolId'])
                    if ticker:
                        # Use lastTradePrice or bidPrice as current price
                        price = quote.get('lastTradePrice') or quote.get('bidPrice')
                        if price:
                            prices[ticker] = float(price)
            except Exception as e:
                error_msg = f"Quote fetch failed: {str(e)[:100]}"
                log_message(f"⚠️  {error_msg}", False)
                send_error_alert("API Quote Error", error_msg, critical=True)
                
    except Exception as e:
        error_msg = f"Error fetching prices: {str(e)[:100]}"
        log_message(f"⚠️  {error_msg}", False)
        send_error_alert("Price Fetch Failed", error_msg, critical=True)
    
    return prices

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
        bid = quote_data.get('bidPrice', 0)
        ask = quote_data.get('askPrice', 0)
        last_price = quote_data.get('lastTradePrice', 0)
        volume = quote_data.get('volume', 0)
        
        # Calculate dollar volume (rough estimate using last price)
        dollar_volume = volume * last_price
        
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

def check_positions(current_prices):
    """Check existing positions for exits"""
    global capital, positions, trades, consecutive_losses, total_closed_trades
    
    exits = []
    for ticker, pos in list(positions.items()):
        if ticker not in current_prices:
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
        exit_value = pos['shares'] * exit_price - COMMISSION
        capital += exit_value
        
        pnl = exit_value - (pos['shares'] * pos['entry_price'] + COMMISSION)
        pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
        
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

def scan_and_trade(historical_data, current_prices, available_capital):
    """Scan for opportunities and enter trades"""
    global capital, positions, consecutive_losses, market_regime_ok
    
    # CIRCUIT BREAKER 1: Check consecutive losses
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        log_message(f"\n🚨 CIRCUIT BREAKER: {consecutive_losses} consecutive losses", False)
        log_message(f"   Trading paused - manual review required", False)
        send_error_alert("Consecutive Losses", f"{consecutive_losses} losing trades in a row", critical=True)
        return
    
    # CIRCUIT BREAKER 2: Check daily portfolio loss
    current_equity = capital + sum(pos['shares'] * current_prices.get(t, pos['entry_price']) 
                                   for t, pos in positions.items())
    daily_loss_pct = (current_equity - daily_start_equity) / daily_start_equity
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
        current_price = current_prices[ticker]
        
        # Calculate position size (supports fractional shares!)
        max_position_value = capital * BASE_POSITION_SIZE_PCT
        
        if FRACTIONAL_SHARES_ENABLED:
            # Fractional shares: allocate exact dollar amount (commission-free)
            shares = max_position_value / current_price
            cost = shares * current_price  # No commission for fractional
        else:
            # Whole shares: traditional calculation
            shares = int((max_position_value - COMMISSION) / current_price)
            cost = shares * current_price + COMMISSION
        
        # Ensure we have at least a minimum position
        if cost >= 1.0 and cost <= capital * 0.85:
            # Only use 85% of capital to leave buffer
                
                # PAPER TRADING: Simulate fill, LIVE TRADING: Place actual order
                if PAPER_TRADING:
                    # Paper mode - instant fill at current price
                    fill_price = current_price
                    log_message(f"   🧪 Paper trade: Simulated fill at ${fill_price:.2f}")
                else:
                    # LIVE MODE - Place actual limit order (NOT IMPLEMENTED YET)
                    log_message(f"   ⚠️ LIVE ORDER EXECUTION NOT YET IMPLEMENTED")
                    log_message(f"   Set PAPER_TRADING=True to simulate")
                    continue
                
                capital -= cost
                
                positions[ticker] = {
                    'shares': shares,
                    'entry_price': fill_price,
                    'entry_date': datetime.now(),
                    'entry_time': datetime.now(),
                    'highest_price': fill_price,
                    'stop_loss': fill_price * (1 - STOP_LOSS_PCT),
                    'take_profit': fill_price * (1 + TAKE_PROFIT_PCT),
                    'trailing_stop': fill_price * (1 - TRAILING_STOP_PCT),
                    'current_price': fill_price,
                    'unrealized_pnl': 0,
                    'unrealized_pnl_pct': 0
                }
                
                # Save position to database
                save_position_to_db(ticker, positions[ticker])
                
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
                    f"     Stop Loss: ${positions[ticker]['stop_loss']:.2f} (-15%)\n"
                    f"     Take Profit: ${positions[ticker]['take_profit']:.2f} (+40%)\n"
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
        
        # Check for remote stop flag
        if Path(REMOTE_STOP_FILE).exists():
            log_message(f"\n🛑 REMOTE STOP DETECTED")
            log_message(f"   Found: {REMOTE_STOP_FILE}")
            log_message(f"   Stopping trading gracefully...")
            
            # Close all positions before stopping
            if positions:
                log_message(f"\n📦 Closing {len(positions)} open positions...")
                current_prices = get_current_prices_questrade(list(positions.keys()))
                for ticker in list(positions.keys()):
                    if ticker in current_prices:
                        check_positions(current_prices)  # Will close positions
            
            # Delete the stop file
            Path(REMOTE_STOP_FILE).unlink()
            log_message(f"   ✅ Stop file removed")
            break
        
        # Check if market is closed (after 4:00 PM EST)
        market_close_hour = 16  # 4 PM in 24-hour format
        if now.hour >= market_close_hour:
            log_message(f"\n🔴 Market closed at 4:00 PM EST")
            log_message(f"   Current time: {current_time}")
            log_message(f"   Stopping live trading...")
            break
        
        log_message(f"\n{'─' * 80}")
        log_message(f"🔍 Check #{checks} at {current_time} (Elapsed: {elapsed_minutes} min)")
        
        # Check market regime (VIX/SPY) - only every 10 checks to reduce overhead
        if checks % 10 == 0:
            market_regime_ok, regime_msg = check_market_regime()
            if not market_regime_ok:
                log_message(f"   ⚠️ Market regime: {regime_msg}")
        
        # Get current prices from Questrade
        log_message("   📊 Fetching live prices from Questrade...")
        current_prices = get_current_prices_questrade(TRADING_UNIVERSE)
        log_message(f"   ✓ Got prices for {len(current_prices)} stocks")
        
        # Check existing positions for exits
        if positions:
            check_positions(current_prices)
            # Update position P&L in database
            for ticker, pos in positions.items():
                if ticker in current_prices:
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
                        check_positions(current_prices)
            
            log_message(f"   🛑 Trading stopped to prevent further losses")
            break
        
        # Scan for new opportunities (pass capital for affordability check)
        scan_and_trade(historical_data, current_prices, capital)
        
        # Current status (recalculate equity after potential trades)
        current_equity = capital
        for ticker, pos in positions.items():
            if ticker in current_prices:
                current_equity += pos['shares'] * current_prices[ticker]
        
        pnl = current_equity - starting_equity
        pnl_pct = (pnl / starting_equity) * 100
        
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
        time.sleep(CHECK_INTERVAL_SECONDS)
        
except KeyboardInterrupt:
    log_message("\n\n⚠️  Test stopped by user")

# Final summary
print_header("📊 FINAL RESULTS")

end_time = datetime.now()
duration = (end_time - start_time).total_seconds() / 60

# Get final prices and calculate final equity
final_prices = get_current_prices_questrade(TRADING_UNIVERSE)
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

if trades:
    log_message(f"\n📋 TRADES EXECUTED: {len(trades)}")
    buys = [t for t in trades if t['action'] == 'BUY']
    sells = [t for t in trades if t['action'] == 'SELL']
    
    log_message(f"\n   Buys: {len(buys)}")
    for trade in buys:
        log_message(f"\n   🟢 BUY {trade['ticker']}")
        log_message(f"      Time: {trade['time']}")
        log_message(f"      Price: ${trade['price']:.2f}")
        log_message(f"      Shares: {trade['shares']}")
        log_message(f"      Cost: ${trade['cost']:,.2f}")
        log_message(f"      Momentum: {trade['momentum']:.4f}")
    
    if sells:
        log_message(f"\n   Sells: {len(sells)}")
        for trade in sells:
            emoji = "🟢" if trade['pnl'] > 0 else "🔴"
            log_message(f"\n   {emoji} SELL {trade['ticker']}")
            log_message(f"      Time: {trade['time']}")
            log_message(f"      Entry: ${trade['entry_price']:.2f}")
            log_message(f"      Exit: ${trade['exit_price']:.2f}")
            log_message(f"      Shares: {trade['shares']}")
            log_message(f"      P&L: ${trade['pnl']:,.2f} ({trade['pnl_pct']:+.2f}%)")
            log_message(f"      Reason: {trade['reason'].replace('_', ' ').title()}")
else:
    log_message(f"\n📋 TRADES EXECUTED: 0")
    log_message(f"   ℹ️  No trades triggered during test period")

if positions:
    log_message(f"\n🔹 OPEN POSITIONS: {len(positions)}")
    for ticker, pos in positions.items():
        if ticker in final_prices:
            current_price = final_prices[ticker]
            unrealized_pnl = (current_price - pos['entry_price']) * pos['shares']
            unrealized_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
            log_message(f"\n   {ticker}:")
            log_message(f"      Entry:      ${pos['entry_price']:.2f}")
            log_message(f"      Current:    ${current_price:.2f}")
            log_message(f"      Shares:     {pos['shares']}")
            log_message(f"      Unrealized: ${unrealized_pnl:+,.2f} ({unrealized_pct:+.2f}%)")
else:
    log_message(f"\n🔹 OPEN POSITIONS: 0")

print_header("✅ Test Complete!")
log_message(f"\n📝 Full log saved to: {log_file}\n")
