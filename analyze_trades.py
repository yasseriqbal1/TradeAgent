"""Analyze backtest trade results."""
import pandas as pd

df = pd.read_csv('backtest_trades.csv')

print('\n' + '='*60)
print('TRADE SUMMARY')
print('='*60)
print(f'Total Trades: {len(df)}')
print(f'Winners: {len(df[df.pnl > 0])} ({len(df[df.pnl > 0])/len(df)*100:.1f}%)')
print(f'Losers: {len(df[df.pnl < 0])} ({len(df[df.pnl < 0])/len(df)*100:.1f}%)')

print(f'\nTotal P&L: ${df.pnl.sum():.2f}')
print(f'Avg Win: ${df[df.pnl > 0].pnl.mean():.2f}')
print(f'Avg Loss: ${df[df.pnl < 0].pnl.mean():.2f}')
print(f'Largest Win: ${df.pnl.max():.2f} ({df.loc[df.pnl.idxmax()].ticker})')
print(f'Largest Loss: ${df.pnl.min():.2f} ({df.loc[df.pnl.idxmin()].ticker})')

print(f'\nAvg Hold Time: {df.hold_days.mean():.1f} days')
print(f'Max Hold Time: {df.hold_days.max():.0f} days')

print('\n' + '='*60)
print('EXIT REASONS')
print('='*60)
print(df.exit_reason.value_counts())

print('\n' + '='*60)
print('BY TICKER')
print('='*60)
ticker_stats = df.groupby('ticker').agg({
    'pnl': ['count', 'sum', 'mean']
}).round(2)
ticker_stats.columns = ['Trades', 'Total P&L', 'Avg P&L']
print(ticker_stats.sort_values('Total P&L', ascending=False))

print('\n' + '='*60)
print('BEST TRADES')
print('='*60)
best = df.nlargest(5, 'pnl')[['ticker', 'entry_date', 'exit_date', 'pnl', 'pnl_pct', 'exit_reason']]
print(best.to_string(index=False))

print('\n' + '='*60)
print('WORST TRADES')
print('='*60)
worst = df.nsmallest(5, 'pnl')[['ticker', 'entry_date', 'exit_date', 'pnl', 'pnl_pct', 'exit_reason']]
print(worst.to_string(index=False))
