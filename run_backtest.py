"""Quick script to run backtest on 9 stocks."""

import requests
import json
from datetime import datetime, timedelta

# Your 9 stocks
tickers = ['NVDA', 'PLTR', 'QBTS', 'QUBT', 'MU', 'RGTI', 'SNOW', 'IONQ', 'LAES']

# Backtest parameters
params = {
    'start_date': '2023-01-01',
    'end_date': '2024-12-30',
    'initial_capital': 100000,
    'max_positions': 3
}

print("🚀 Running backtest on 9 stocks...")
print(f"Tickers: {', '.join(tickers)}")
print(f"Period: {params['start_date']} to {params['end_date']}")
print(f"Capital: ${params['initial_capital']:,}")
print("\nSending request to FastAPI...")

# Build query parameters with multiple tickers
query = params.copy()
for i, ticker in enumerate(tickers):
    query[f'tickers'] = tickers

print(f"\nQuery params: {query}")

# Make request
response = requests.post(
    'http://127.0.0.1:8001/backtest/run',
    params=query
)

print(f"\nStatus Code: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    
    print("\n" + "="*60)
    print("📊 BACKTEST RESULTS")
    print("="*60)
    
    metrics = result['metrics']
    
    # Overview
    print(f"\n💰 OVERVIEW:")
    print(f"  Total Trades: {metrics['overview']['total_trades']}")
    print(f"  Total Return: {metrics['overview']['total_return_pct']:.2f}%")
    print(f"  Final Equity: ${metrics['overview']['final_equity']:,.2f}")
    print(f"  Net Profit: ${metrics['overview']['net_profit']:,.2f}")
    
    # Risk-Adjusted
    print(f"\n📈 RISK-ADJUSTED:")
    print(f"  Sharpe Ratio: {metrics['risk_adjusted']['sharpe_ratio']:.2f} (target: ≥1.5)")
    print(f"  Max Drawdown: {metrics['risk_adjusted']['max_drawdown_pct']:.2f}% (target: ≤20%)")
    print(f"  Calmar Ratio: {metrics['risk_adjusted']['calmar_ratio']:.2f}")
    
    # Trade Quality
    print(f"\n🎯 TRADE QUALITY:")
    print(f"  Win Rate: {metrics['trade_quality']['win_rate_pct']:.2f}% (target: ≥45%)")
    print(f"  Profit Factor: {metrics['trade_quality']['profit_factor']:.2f} (target: ≥1.5)")
    print(f"  Avg Win: ${metrics['trade_quality']['avg_win']:.2f}")
    print(f"  Avg Loss: ${metrics['trade_quality']['avg_loss']:.2f}")
    
    # Validation
    print(f"\n✅ VALIDATION:")
    val = metrics['validation']
    print(f"  Sharpe ≥1.5: {'✓' if val['meets_sharpe_target'] else '✗'}")
    print(f"  Drawdown ≤20%: {'✓' if val['meets_drawdown_target'] else '✗'}")
    print(f"  Win Rate ≥45%: {'✓' if val['meets_win_rate_target'] else '✗'}")
    print(f"  Profit Factor ≥1.5: {'✓' if val['meets_profit_factor_target'] else '✗'}")
    print(f"\n  PASSES ALL CRITERIA: {'🎉 YES' if val['passes_all_criteria'] else '❌ NO'}")
    
    # Save results
    with open('backtest_results.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n💾 Full results saved to: backtest_results.json")
    
else:
    print(f"\n❌ Error: {response.text}")
