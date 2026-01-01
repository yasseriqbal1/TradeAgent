"""Direct backtest test without API."""

import sys
from datetime import datetime
from loguru import logger
from quant_agent.backtest_engine import Backtester, BacktestConfig
from quant_agent.performance_metrics import PerformanceMetrics

# Enable INFO logging to see progress
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}\n"
)

print("Running direct backtest...")

# Your 9 stocks
tickers = ['NVDA', 'PLTR', 'QBTS', 'QUBT', 'MU', 'RGTI', 'SNOW', 'IONQ', 'LAES']

# Config
config = BacktestConfig(
    initial_capital=100000,
    max_positions=3,
    min_score_threshold=0.0,  # Lower threshold to allow trades
    enable_regime_filter=False,  # Disable for now (needs SPY data)
    enable_correlation_filter=True,
    enable_earnings_filter=False  # Disable (Yahoo rate limit)
)

# Create backtester
backtester = Backtester(config=config)

# Date range (Questrade limitation: only ~60 days available)
from datetime import timedelta
end_date = datetime(2025, 12, 26)  # Last date with data
start_date = datetime(2025, 11, 1)  # ~60 days (maximum available)

print(f"Loading historical data for {len(tickers)} tickers...")
print(f"Period: {start_date.date()} to {end_date.date()}")

# Load data (use Questrade cached data for available history)
data = backtester.load_historical_data(
    tickers=tickers,
    start_date=start_date,
    end_date=end_date,
    force_refresh=False
)

print(f"OK Loaded {len(data)} tickers")
print("\nRunning simulation...")

# Run backtest
backtester.simulate_trades(
    data=data,
    start_date=start_date,
    end_date=end_date
)

# Get results
trades = backtester.get_trade_log()
equity_curve = backtester.get_equity_curve()

print(f"\nOK Simulation complete: {len(trades)} trades")

# Calculate metrics
metrics = PerformanceMetrics.calculate_comprehensive_metrics(
    trades=trades,
    equity_curve=equity_curve,
    initial_capital=config.initial_capital,
    start_date=start_date,
    end_date=end_date
)

# Display results
print("\n" + "="*60)
print("BACKTEST RESULTS")
print("="*60)

print(f"\nOVERVIEW:")
print(f"  Total Trades: {metrics['overview']['total_trades']}")
print(f"  Total Return: {metrics['overview']['total_return_pct']:.2f}%")
print(f"  Final Equity: ${metrics['overview']['final_equity']:,.2f}")
print(f"  Net Profit: ${metrics['overview']['net_profit']:,.2f}")

print(f"\nRISK-ADJUSTED:")
print(f"  Sharpe Ratio: {metrics['risk_adjusted']['sharpe_ratio']:.2f} (target: >=1.5)")
print(f"  Max Drawdown: {metrics['risk_adjusted']['max_drawdown_pct']:.2f}% (target: <=20%)")
print(f"  Calmar Ratio: {metrics['risk_adjusted']['calmar_ratio']:.2f}")

print(f"\nTRADE QUALITY:")
print(f"  Win Rate: {metrics['trade_quality']['win_rate_pct']:.2f}% (target: >=45%)")
print(f"  Profit Factor: {metrics['trade_quality']['profit_factor']:.2f} (target: >=1.5)")
print(f"  Avg Win: ${metrics['trade_quality']['avg_win']:.2f}")
print(f"  Avg Loss: ${metrics['trade_quality']['avg_loss']:.2f}")

print(f"\nVALIDATION:")
val = metrics['validation']
print(f"  Sharpe >=1.5: {'YES' if val['meets_sharpe_target'] else 'NO'}")
print(f"  Drawdown <=20%: {'YES' if val['meets_drawdown_target'] else 'NO'}")
print(f"  Win Rate >=45%: {'YES' if val['meets_win_rate_target'] else 'NO'}")
print(f"  Profit Factor >=1.5: {'YES' if val['meets_profit_factor_target'] else 'NO'}")
print(f"\n  PASSES ALL CRITERIA: {'*** YES ***' if val['passes_all_criteria'] else '*** NO ***'}")

# Save results
import json
with open('backtest_results_direct.json', 'w') as f:
    json.dump(metrics, f, indent=2, default=str)

print(f"\nResults saved to: backtest_results_direct.json")

# Save trades
trades.to_csv('backtest_trades.csv', index=False)
print(f"Trades saved to: backtest_trades.csv")
