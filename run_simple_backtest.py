"""
Simple backtest using local historical data.
No API needed - reads directly from CSV files.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from glob import glob

# Configuration
INITIAL_CAPITAL = 100000
MAX_POSITIONS = 3
BASE_POSITION_SIZE_PCT = 0.25  # 25% base per position
COMMISSION = 1.0  # $1 per trade

# Risk Controls
STOP_LOSS_PCT = 0.15  # 15% stop loss
TAKE_PROFIT_PCT = 0.40  # 40% take profit
TRAILING_STOP_PCT = 0.12  # 12% trailing stop
MAX_POSITION_RISK = 0.05  # 5% max risk per position
MAX_PORTFOLIO_LOSS_PCT = 0.08  # 8% max portfolio loss in a day
MIN_VOLUME_RATIO = 1.0  # Minimum volume ratio (1.0x average)
MAX_VOLATILITY = 0.06  # Maximum daily volatility (6%)

# Sector Exclusions
EXCLUDED_SECTORS = ['Finance', 'Banking', 'Insurance']  # No financial institutions

# Sector Classification (expand as you add more tickers)
SECTOR_MAP = {
    # Technology
    'AAPL': 'Technology', 'MSFT': 'Technology', 'NVDA': 'Technology',
    'AMD': 'Technology', 'GOOG': 'Technology', 'META': 'Technology',
    'MU': 'Technology', 'PLTR': 'Technology', 'SNOW': 'Technology',
    'CRWD': 'Technology', 'DDOG': 'Technology', 'NET': 'Technology',
    'SHOP': 'Technology', 'ADBE': 'Technology', 'CRM': 'Technology',
    'ORCL': 'Technology', 'AVGO': 'Technology', 'INTC': 'Technology',
    'CSCO': 'Technology',
    
    # Quantum Computing
    'IONQ': 'Quantum Computing', 'QBTS': 'Quantum Computing',
    'QUBT': 'Quantum Computing', 'RGTI': 'Quantum Computing',
    'LAES': 'Quantum Computing',
    
    # Healthcare
    'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'LLY': 'Healthcare',
    'ABBV': 'Healthcare', 'TMO': 'Healthcare', 'PFE': 'Healthcare',
    'MRK': 'Healthcare',
    
    # Energy
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'SLB': 'Energy',
    
    # Industrials
    'CAT': 'Industrials', 'BA': 'Industrials', 'UPS': 'Industrials',
    'GE': 'Industrials', 'HON': 'Industrials',
    
    # Consumer
    'TSLA': 'Consumer', 'AMZN': 'Consumer', 'WMT': 'Consumer',
    'HD': 'Consumer', 'NKE': 'Consumer', 'SBUX': 'Consumer',
    'DIS': 'Consumer', 'TGT': 'Consumer', 'COST': 'Consumer',
    
    # Finance/Banking (EXCLUDED)
    'JPM': 'Finance', 'BAC': 'Finance', 'GS': 'Finance',
    'MS': 'Finance', 'WFC': 'Finance', 'C': 'Finance',
    'V': 'Finance', 'MA': 'Finance', 'AXP': 'Finance',
    'BLK': 'Finance', 'SCHW': 'Finance', 'USB': 'Finance',
}

print("=" * 80)
print("📊 SIMPLE MOMENTUM BACKTEST")
print("=" * 80)

# Load historical data
data_dir = "historical_data"
csv_files = glob(os.path.join(data_dir, "historical_data_*.csv"))

print(f"\n📁 Loading data from {len(csv_files)} files...")

# Load all data and filter by sector
all_data = {}
for csv_file in csv_files:
    filename = os.path.basename(csv_file)
    ticker = filename.replace("historical_data_", "").replace(".csv", "")
    
    # Check if ticker is in excluded sector
    sector = SECTOR_MAP.get(ticker, 'Unknown')
    if sector in EXCLUDED_SECTORS:
        print(f"  ⊗ {ticker}: Skipped ({sector} - excluded sector)")
        continue
    
    df = pd.read_csv(csv_file, index_col='Date', parse_dates=True)
    all_data[ticker] = df
    print(f"  ✓ {ticker}: {len(df)} days ({sector})")

tickers = sorted(all_data.keys())
print(f"\n✅ Loaded {len(tickers)} tickers: {', '.join(tickers)}")

# Backtest period (use last 2 years for faster testing)
start_date = pd.Timestamp('2023-01-01')
end_date = pd.Timestamp('2024-12-31')

print(f"\n📅 Backtest Period: {start_date.date()} to {end_date.date()}")

# Calculate momentum scores for all tickers
print("\n🧮 Calculating momentum factors...")

momentum_data = {}
for ticker, df in all_data.items():
    # Filter to backtest period
    df_period = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    
    if len(df_period) < 60:  # Need at least 60 days
        continue
    
    # Calculate momentum factors
    df_period['returns_20d'] = df_period['Close'].pct_change(20)
    df_period['returns_60d'] = df_period['Close'].pct_change(60)
    df_period['momentum_score'] = (
        0.5 * df_period['returns_20d'] + 
        0.5 * df_period['returns_60d']
    )
    
    # Volume trend
    df_period['volume_ma20'] = df_period['Volume'].rolling(20).mean()
    df_period['volume_ratio'] = df_period['Volume'] / df_period['volume_ma20']
    
    # Volatility (for position sizing)
    df_period['volatility'] = df_period['Close'].pct_change().rolling(20).std()
    
    momentum_data[ticker] = df_period

print(f"  ✓ Calculated for {len(momentum_data)} tickers")

# Simple momentum strategy with risk controls
print("\n🎯 Running Strategy: Top 3 Momentum Stocks (20-day rebalance)")
print(f"  Capital: ${INITIAL_CAPITAL:,}")
print(f"  Max Positions: {MAX_POSITIONS}")
print(f"  Base Position Size: {BASE_POSITION_SIZE_PCT*100:.0f}% each")
print(f"\n🛡️  Risk Controls:")
print(f"  Stop Loss: {STOP_LOSS_PCT*100:.0f}%")
print(f"  Take Profit: {TAKE_PROFIT_PCT*100:.0f}%")
print(f"  Trailing Stop: {TRAILING_STOP_PCT*100:.0f}%")
print(f"  Max Position Risk: {MAX_POSITION_RISK*100:.0f}%")
print(f"  Max Daily Portfolio Loss: {MAX_PORTFOLIO_LOSS_PCT*100:.0f}%")
print(f"\n🚫 Excluded Sectors: {', '.join(EXCLUDED_SECTORS)}")

# Get all unique dates
all_dates = sorted(set().union(*[set(df.index) for df in momentum_data.values()]))
backtest_dates = [d for d in all_dates if start_date <= d <= end_date]

# Initialize tracking
capital = INITIAL_CAPITAL
positions = {}  # ticker -> {'shares': int, 'entry_price': float, 'entry_date': date, 'highest_price': float, 'stop_loss': float, 'take_profit': float}
trades = []
equity_curve = []
daily_pnl_history = []

rebalance_interval = 20  # days
last_rebalance = None
stop_loss_exits = 0
take_profit_exits = 0
trailing_stop_exits = 0

for current_date in backtest_dates[60:]:  # Start after momentum lookback period
    
    prev_equity = equity_curve[-1]['equity'] if equity_curve else INITIAL_CAPITAL
    
    # Check stop losses, take profits, and trailing stops FIRST
    positions_to_close = []
    for ticker, pos in list(positions.items()):
        if current_date in momentum_data[ticker].index:
            current_price = momentum_data[ticker].loc[current_date, 'Close']
            
            # Update highest price for trailing stop
            if current_price > pos['highest_price']:
                pos['highest_price'] = current_price
                # Update trailing stop
                pos['trailing_stop'] = current_price * (1 - TRAILING_STOP_PCT)
            
            # Check stop loss
            if current_price <= pos['stop_loss']:
                positions_to_close.append((ticker, current_price, 'stop_loss'))
                stop_loss_exits += 1
            # Check take profit
            elif current_price >= pos['take_profit']:
                positions_to_close.append((ticker, current_price, 'take_profit'))
                take_profit_exits += 1
            # Check trailing stop
            elif current_price <= pos['trailing_stop']:
                positions_to_close.append((ticker, current_price, 'trailing_stop'))
                trailing_stop_exits += 1
    
    # Execute risk-based exits
    for ticker, exit_price, exit_reason in positions_to_close:
        pos = positions[ticker]
        exit_value = pos['shares'] * exit_price - COMMISSION
        capital += exit_value
        
        # Record trade
        pnl = exit_value - (pos['shares'] * pos['entry_price'] + COMMISSION)
        pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
        hold_days = (current_date - pos['entry_date']).days
        
        trades.append({
            'ticker': ticker,
            'entry_date': pos['entry_date'],
            'entry_price': pos['entry_price'],
            'exit_date': current_date,
            'exit_price': exit_price,
            'shares': pos['shares'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'hold_days': hold_days,
            'exit_reason': exit_reason
        })
        
        del positions[ticker]
    
    # Check for rebalancing
    should_rebalance = (
        last_rebalance is None or 
        (current_date - last_rebalance).days >= rebalance_interval
    )
    
    if should_rebalance:
        # Close all positions
        if positions:
            for ticker, pos in positions.items():
                if current_date in momentum_data[ticker].index:
                    exit_price = momentum_data[ticker].loc[current_date, 'Close']
                    exit_value = pos['shares'] * exit_price - COMMISSION
                    capital += exit_value
                    
                    # Record trade
                    pnl = exit_value - (pos['shares'] * pos['entry_price'] + COMMISSION)
                    pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
                    hold_days = (current_date - pos['entry_date']).days
                    
                    trades.append({
                        'ticker': ticker,
                        'entry_date': pos['entry_date'],
                        'entry_price': pos['entry_price'],
                        'exit_date': current_date,
                        'exit_price': exit_price,
                        'shares': pos['shares'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'hold_days': hold_days,
                        'exit_reason': 'rebalance'
                    })
        
        positions = {}
        
        # Calculate scores for all tickers with risk filters
        scores = {}
        for ticker, df in momentum_data.items():
            if current_date in df.index:
                row = df.loc[current_date]
                # Risk filters: volume, volatility, positive momentum
                if (pd.notna(row['momentum_score']) and 
                    row['momentum_score'] > 0 and  # Only positive momentum
                    row['volume_ratio'] >= MIN_VOLUME_RATIO and  # Sufficient volume
                    row['volatility'] < MAX_VOLATILITY):  # Not too volatile
                    scores[ticker] = row['momentum_score']
        
        # Select top 3
        top_tickers = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:MAX_POSITIONS]
        
        # Open new positions with volatility-adjusted sizing
        for ticker, score in top_tickers:
            if current_date in momentum_data[ticker].index:
                row = momentum_data[ticker].loc[current_date]
                entry_price = row['Close']
                volatility = row['volatility']
                
                # Adjust position size based on volatility
                # Lower volatility = larger position, higher volatility = smaller position
                volatility_multiplier = min(1.0, 0.03 / max(volatility, 0.01))
                adjusted_position_pct = BASE_POSITION_SIZE_PCT * volatility_multiplier
                
                # Calculate position size based on max risk per position
                position_value = min(
                    capital * adjusted_position_pct,
                    (capital * MAX_POSITION_RISK) / STOP_LOSS_PCT
                )
                
                shares = int((position_value - COMMISSION) / entry_price)
                
                if shares > 0:
                    cost = shares * entry_price + COMMISSION
                    
                    # Don't enter if it would use more than 85% of capital
                    if cost <= capital * 0.85:
                        capital -= cost
                        
                        positions[ticker] = {
                            'shares': shares,
                            'entry_price': entry_price,
                            'entry_date': current_date,
                            'highest_price': entry_price,
                            'stop_loss': entry_price * (1 - STOP_LOSS_PCT),
                            'take_profit': entry_price * (1 + TAKE_PROFIT_PCT),
                            'trailing_stop': entry_price * (1 - TRAILING_STOP_PCT)
                        }
        
        last_rebalance = current_date
    
    # Calculate current equity
    current_equity = capital
    for ticker, pos in positions.items():
        if current_date in momentum_data[ticker].index:
            current_price = momentum_data[ticker].loc[current_date, 'Close']
            current_equity += pos['shares'] * current_price
    
    equity_curve.append({
        'date': current_date,
        'equity': current_equity
    })
    
    # Track daily P&L
    daily_pnl = current_equity - prev_equity
    daily_pnl_pct = (daily_pnl / prev_equity) * 100 if prev_equity > 0 else 0
    daily_pnl_history.append(daily_pnl_pct)
    
    # Emergency exit if daily loss exceeds limit
    if daily_pnl_pct < -MAX_PORTFOLIO_LOSS_PCT * 100:
        # Close all positions immediately
        for ticker in list(positions.keys()):
            if current_date in momentum_data[ticker].index:
                pos = positions[ticker]
                exit_price = momentum_data[ticker].loc[current_date, 'Close']
                exit_value = pos['shares'] * exit_price - COMMISSION
                capital += exit_value
                
                pnl = exit_value - (pos['shares'] * pos['entry_price'] + COMMISSION)
                pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
                hold_days = (current_date - pos['entry_date']).days
                
                trades.append({
                    'ticker': ticker,
                    'entry_date': pos['entry_date'],
                    'entry_price': pos['entry_price'],
                    'exit_date': current_date,
                    'exit_price': exit_price,
                    'shares': pos['shares'],
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'hold_days': hold_days,
                    'exit_reason': 'emergency_exit'
                })
        
        positions = {}
        last_rebalance = current_date

# Close any remaining positions at end
if positions:
    for ticker, pos in positions.items():
        if end_date in momentum_data[ticker].index:
            exit_price = momentum_data[ticker].loc[end_date, 'Close']
            exit_value = pos['shares'] * exit_price - COMMISSION
            capital += exit_value
            
            pnl = exit_value - (pos['shares'] * pos['entry_price'] + COMMISSION)
            pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
            hold_days = (end_date - pos['entry_date']).days
            
            trades.append({
                'ticker': ticker,
                'entry_date': pos['entry_date'],
                'entry_price': pos['entry_price'],
                'exit_date': end_date,
                'exit_price': exit_price,
                'shares': pos['shares'],
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': hold_days,
                'exit_reason': 'end_of_backtest'
            })

final_equity = capital

# Calculate metrics
print("\n" + "=" * 80)
print("📊 BACKTEST RESULTS")
print("=" * 80)

# Convert to DataFrames
trades_df = pd.DataFrame(trades)
equity_df = pd.DataFrame(equity_curve)

# Overview metrics
total_return = ((final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
net_profit = final_equity - INITIAL_CAPITAL

print(f"\n💰 OVERVIEW:")
print(f"  Initial Capital:  ${INITIAL_CAPITAL:,.2f}")
print(f"  Final Equity:     ${final_equity:,.2f}")
print(f"  Net Profit:       ${net_profit:,.2f}")
print(f"  Total Return:     {total_return:+.2f}%")
print(f"  Total Trades:     {len(trades_df)}")

# Win/Loss metrics
if len(trades_df) > 0:
    winning_trades = trades_df[trades_df['pnl'] > 0]
    losing_trades = trades_df[trades_df['pnl'] <= 0]
    
    win_rate = (len(winning_trades) / len(trades_df)) * 100
    avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
    avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
    
    gross_wins = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
    gross_losses = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 1
    profit_factor = gross_wins / gross_losses if gross_losses != 0 else 0
    
    print(f"\n🎯 TRADE QUALITY:")
    print(f"  Winning Trades:   {len(winning_trades)} ({win_rate:.1f}%)")
    print(f"  Losing Trades:    {len(losing_trades)} ({100-win_rate:.1f}%)")
    print(f"  Average Win:      ${avg_win:,.2f}")
    print(f"  Average Loss:     ${avg_loss:,.2f}")
    print(f"  Profit Factor:    {profit_factor:.2f}")
    
    print(f"\n🛡️  RISK MANAGEMENT:")
    print(f"  Stop Loss Exits:     {stop_loss_exits}")
    print(f"  Take Profit Exits:   {take_profit_exits}")
    print(f"  Trailing Stop Exits: {trailing_stop_exits}")
    print(f"  Rebalance Exits:     {len(trades_df[trades_df['exit_reason'] == 'rebalance'])}")
    
    # Best/Worst trades
    best_trade = trades_df.loc[trades_df['pnl'].idxmax()]
    worst_trade = trades_df.loc[trades_df['pnl'].idxmin()]
    
    print(f"\n🏆 BEST TRADE:")
    print(f"  {best_trade['ticker']}: ${best_trade['pnl']:,.2f} ({best_trade['pnl_pct']:+.2f}%)")
    print(f"  Entry: {best_trade['entry_date'].date()} @ ${best_trade['entry_price']:.2f}")
    print(f"  Exit:  {best_trade['exit_date'].date()} @ ${best_trade['exit_price']:.2f}")
    
    print(f"\n📉 WORST TRADE:")
    print(f"  {worst_trade['ticker']}: ${worst_trade['pnl']:,.2f} ({worst_trade['pnl_pct']:+.2f}%)")
    print(f"  Entry: {worst_trade['entry_date'].date()} @ ${worst_trade['entry_price']:.2f}")
    print(f"  Exit:  {worst_trade['exit_date'].date()} @ ${worst_trade['exit_price']:.2f}")
    
    # Risk metrics
    equity_df['returns'] = equity_df['equity'].pct_change()
    returns = equity_df['returns'].dropna()
    
    if len(returns) > 0:
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() != 0 else 0
        
        # Calculate drawdown
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        print(f"\n📈 RISK-ADJUSTED:")
        print(f"  Sharpe Ratio:     {sharpe_ratio:.2f} (target: ≥1.5)")
        print(f"  Max Drawdown:     {max_drawdown:.2f}% (target: ≤20%)")
        print(f"  Calmar Ratio:     {(total_return / abs(max_drawdown)):.2f}" if max_drawdown != 0 else "  Calmar Ratio:     N/A")
        
        # Validation
        print(f"\n✅ VALIDATION:")
        meets_sharpe = sharpe_ratio >= 1.5
        meets_drawdown = max_drawdown >= -20
        meets_win_rate = win_rate >= 45
        meets_profit_factor = profit_factor >= 1.5
        
        print(f"  Sharpe ≥1.5:         {'✓ PASS' if meets_sharpe else '✗ FAIL'}")
        print(f"  Drawdown ≤20%:       {'✓ PASS' if meets_drawdown else '✗ FAIL'}")
        print(f"  Win Rate ≥45%:       {'✓ PASS' if meets_win_rate else '✗ FAIL'}")
        print(f"  Profit Factor ≥1.5:  {'✓ PASS' if meets_profit_factor else '✗ FAIL'}")
        
        passes_all = meets_sharpe and meets_drawdown and meets_win_rate and meets_profit_factor
        print(f"\n  {'🎉 PASSES ALL CRITERIA!' if passes_all else '⚠️  NEEDS IMPROVEMENT'}")

# Ticker performance
if len(trades_df) > 0 and 'ticker' in trades_df.columns:
    print(f"\n📊 TICKER PERFORMANCE:")
    ticker_stats = trades_df.groupby('ticker').agg({
        'pnl': ['sum', 'count', 'mean'],
        'pnl_pct': 'mean'
    }).round(2)
    ticker_stats.columns = ['Total P&L', 'Trades', 'Avg P&L', 'Avg Return %']
    ticker_stats = ticker_stats.sort_values('Total P&L', ascending=False)
    print(ticker_stats.to_string())
else:
    print(f"\n⚠️  No trades executed - check data quality and momentum thresholds")

# Save results
trades_df.to_csv('backtest_trades.csv', index=False)
equity_df.to_csv('backtest_equity_curve.csv', index=False)

print(f"\n💾 Results saved:")
print(f"  - backtest_trades.csv")
print(f"  - backtest_equity_curve.csv")

print("\n" + "=" * 80)
print("✅ Backtest Complete!")
print("=" * 80)
