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

# Import existing modules
from quant_agent.questrade_loader import QuestradeAPI
from quant_agent.config_loader import ConfigLoader

# Configuration
INITIAL_CAPITAL = 100000
MAX_POSITIONS = 3
BASE_POSITION_SIZE_PCT = 0.25
COMMISSION = 1.0

# Risk Controls
STOP_LOSS_PCT = 0.15
TAKE_PROFIT_PCT = 0.40
TRAILING_STOP_PCT = 0.12
MIN_VOLUME_RATIO = 0.3  # Relaxed for midday trading
MAX_VOLATILITY = 0.06

# Trading Schedule
CHECK_INTERVAL_SECONDS = 60  # Check every 1 minute
RUN_CONTINUOUS = True  # Set to False for timed tests

# n8n Webhook Configuration
N8N_WEBHOOK_ENABLED = True
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/trade-alerts"

# Optimized 25-Stock Universe (Technology, Quantum, Consumer)
TRADING_UNIVERSE = [
    # Technology (13 stocks)
    'AAPL', 'AMD', 'CRWD', 'DDOG', 'GOOG', 'META', 'MSFT', 
    'MU', 'NET', 'NVDA', 'PLTR', 'SHOP', 'SNOW',
    # Quantum Computing (5 stocks)
    'IONQ', 'LAES', 'QBTS', 'QUBT', 'RGTI',
    # Consumer (7 stocks)
    'AMZN', 'DIS', 'HD', 'NKE', 'SBUX', 'TSLA', 'WMT',
]

# Sector Exclusions
EXCLUDED_SECTORS = ['Finance', 'Banking', 'Insurance']

# Initialize trade log
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"trades_log_{timestamp}.txt"

def log_message(message, print_too=True):
    """Write message to log file and optionally print"""
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")
    if print_too:
        print(message)

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

print_header("🔴 LIVE PAPER TRADING TEST (1 HOUR) - USING QUESTRADE")

# Initialize
start_time = datetime.now()
log_message(f"\n⏰ Start Time: {start_time.strftime('%I:%M:%S %p EST')}")
log_message(f"💰 Paper Capital: ${INITIAL_CAPITAL:,}")
log_message(f"📊 Max Positions: {MAX_POSITIONS}")
log_message(f"🔄 Check Interval: {CHECK_INTERVAL_SECONDS} seconds")
log_message(f"📝 Trade Log: {log_file}")
log_message(f"⚠️  Press Ctrl+C to stop")

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
    log_message(f"❌ Failed to connect to Questrade: {e}")
    log_message("   Please check your .env file has valid QUESTRADE_REFRESH_TOKEN")
    exit(1)

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

# Initialize tracking
capital = INITIAL_CAPITAL
positions = {}
trades = []
checks = 0

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
                errors.append(f"{ticker}: Search error - {str(e)[:50]}")
        
        # Log search results
        if len(symbol_ids) == 0:
            log_message(f"   ⚠️  No symbols found on Questrade. This might be because:", False)
            log_message(f"      - US stocks need to be searched with exchange (e.g., AAPL on NASDAQ)", False)
            log_message(f"      - Questrade practice account has limited symbol access", False)
            log_message(f"      - API credentials might be for Canadian markets only", False)
            if errors[:3]:  # Show first 3 errors
                for err in errors[:3]:
                    log_message(f"      - {err}", False)
            return prices
        
        # Get quotes for all symbols
        if symbol_ids:
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
        log_message(f"⚠️  Error fetching prices: {str(e)[:100]}", False)
    
    return prices

def check_positions(current_prices):
    """Check existing positions for exits"""
    global capital, positions, trades
    
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
        print_alert(
            f"SELL {ticker} @ ${exit_price:.2f}\n"
            f"     Reason: {reason.replace('_', ' ').title()}\n"
            f"     Shares: {pos['shares']}\n"
            f"     Entry: ${pos['entry_price']:.2f}\n"
            f"     P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
            f"     Capital: ${capital:,.2f}",
            emoji
        )
        
        del positions[ticker]

def scan_and_trade(historical_data, current_prices):
    """Scan for opportunities and enter trades"""
    global capital, positions
    
    # Don't trade if we're at max positions
    if len(positions) >= MAX_POSITIONS:
        return
    
    # Calculate scores for all stocks
    scores = {}
    candidates_checked = 0
    reasons = {}
    
    for ticker, df in historical_data.items():
        if ticker in positions:
            continue
        if ticker not in current_prices:
            continue
        
        candidates_checked += 1
        current_price = current_prices[ticker]
        
        # Update dataframe with current price for today's action
        momentum, volume_ratio, volatility = calculate_momentum_score(df, current_price)
        
        # Debug: Track why stocks fail
        if momentum is None:
            reasons[ticker] = "Insufficient data"
        elif momentum <= 0:
            reasons[ticker] = f"Momentum too low ({momentum:.4f})"
        elif volume_ratio < MIN_VOLUME_RATIO:
            reasons[ticker] = f"Volume too low ({volume_ratio:.2f})"
        elif volatility >= MAX_VOLATILITY:
            reasons[ticker] = f"Volatility too high ({volatility:.4f})"
        else:
            scores[ticker] = momentum
    
    # Log scan results
    log_message(f"   🔍 Scanned {candidates_checked} stocks", False)
    if scores:
        log_message(f"   ✅ Found {len(scores)} candidates with positive momentum", False)
        top_3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        for ticker, mom in top_3:
            log_message(f"      • {ticker}: momentum={mom:.4f}", False)
    else:
        log_message(f"   ⚠️  No candidates met criteria", False)
        # Show top 3 rejection reasons
        sample_reasons = list(reasons.items())[:3]
        for ticker, reason in sample_reasons:
            log_message(f"      • {ticker}: {reason}", False)
    
    if not scores:
        return
    
    # Get top opportunities
    top_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    available_slots = MAX_POSITIONS - len(positions)
    
    for ticker, score in top_stocks[:available_slots]:
        current_price = current_prices[ticker]
        
        # Calculate position size
        position_value = capital * BASE_POSITION_SIZE_PCT
        shares = int((position_value - COMMISSION) / current_price)
        
        if shares > 0:
            cost = shares * current_price + COMMISSION
            
            if cost <= capital * 0.85:
                capital -= cost
                
                positions[ticker] = {
                    'shares': shares,
                    'entry_price': current_price,
                    'entry_time': datetime.now(),
                    'highest_price': current_price,
                    'stop_loss': current_price * (1 - STOP_LOSS_PCT),
                    'take_profit': current_price * (1 + TAKE_PROFIT_PCT),
                    'trailing_stop': current_price * (1 - TRAILING_STOP_PCT)
                }
                
                trade = {
                    'time': datetime.now().strftime('%I:%M:%S %p'),
                    'action': 'BUY',
                    'ticker': ticker,
                    'price': current_price,
                    'shares': shares,
                    'cost': cost,
                    'momentum': score
                }
                trades.append(trade)
                
                # Send webhook notification
                webhook_data = {
                    'action': 'BUY',
                    'ticker': ticker,
                    'price': current_price,
                    'shares': shares,
                    'momentum': score
                }
                send_webhook(webhook_data)
                
                print_alert(
                    f"BUY {ticker} @ ${current_price:.2f}\n"
                    f"     Momentum Score: {score:.4f}\n"
                    f"     Shares: {shares}\n"
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
    while True:  # Run continuously until Ctrl+C or market close
        checks += 1
        now = datetime.now()
        current_time = now.strftime('%I:%M:%S %p')
        elapsed_minutes = int((now - start_time).total_seconds() / 60)
        
        # Check if market is closed (after 4:00 PM EST)
        # TEMPORARILY DISABLED FOR TESTING
        market_close_hour = 16  # 4 PM in 24-hour format
        if now.hour >= market_close_hour:
            log_message(f"\n🔴 Market closed at 4:00 PM EST")
            log_message(f"   Current time: {current_time}")
            log_message(f"   Stopping live trading...")
            break
        
        log_message(f"\n{'─' * 80}")
        log_message(f"🔍 Check #{checks} at {current_time} (Elapsed: {elapsed_minutes} min)")
        
        # Get current prices from Questrade
        log_message("   📊 Fetching live prices from Questrade...")
        current_prices = get_current_prices_questrade(TRADING_UNIVERSE)
        log_message(f"   ✓ Got prices for {len(current_prices)} stocks")
        
        # Check existing positions for exits
        if positions:
            check_positions(current_prices)
        
        # Scan for new opportunities
        scan_and_trade(historical_data, current_prices)
        
        # Current status
        current_equity = capital
        for ticker, pos in positions.items():
            if ticker in current_prices:
                current_equity += pos['shares'] * current_prices[ticker]
        
        pnl = current_equity - INITIAL_CAPITAL
        pnl_pct = (pnl / INITIAL_CAPITAL) * 100
        
        log_message(f"\n   📈 Current Status:")
        log_message(f"      Equity: ${current_equity:,.2f}")
        log_message(f"      P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
        log_message(f"      Cash: ${capital:,.2f}")
        log_message(f"      Positions: {len(positions)}/{MAX_POSITIONS}")
        
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
log_message(f"   Starting Capital: ${INITIAL_CAPITAL:,.2f}")
log_message(f"   Ending Equity:    ${final_equity:,.2f}")
log_message(f"   Net P&L:          ${final_equity - INITIAL_CAPITAL:+,.2f}")
log_message(f"   Return:           {((final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100):+.2f}%")

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
