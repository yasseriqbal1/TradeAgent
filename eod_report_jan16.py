import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname='tradeagent',
    user='postgres',
    password='yasser',
    host='localhost'
)

cur = conn.cursor()

print("\n" + "="*80)
print(f"COMPLETE DAY TRADES - January 16, 2026")
print("="*80 + "\n")

# Get all trades today
cur.execute("""
    SELECT 
        TO_CHAR(trade_date, 'HH12:MI AM') as time,
        ticker,
        action,
        shares,
        price,
        pnl,
        pnl_pct,
        notes
    FROM trades_history
    WHERE DATE(trade_date) = '2026-01-16'
    ORDER BY trade_date
""")

trades = cur.fetchall()
print(f"Total trades today: {len(trades)}\n")

buys = [t for t in trades if t[2] == 'BUY']
sells = [t for t in trades if t[2] == 'SELL']

print(f"BUYS: {len(buys)}")
for trade in buys:
    time, ticker, action, shares, price, pnl, pnl_pct, notes = trade
    print(f"  {time}: {ticker} - {shares:.4f} shares @ ${price:.2f} = ${shares * price:.2f}")

print(f"\nSELLS: {len(sells)}")
for trade in sells:
    time, ticker, action, shares, price, pnl, pnl_pct, notes = trade
    pnl_str = f"${pnl:.2f}" if pnl else "$0.00"
    pct_str = f"({pnl_pct:.2f}%)" if pnl_pct else "(0.00%)"
    status = "🟢" if pnl and pnl > 0 else "🔴"
    print(f"  {status} {time}: {ticker} - {shares:.4f} shares @ ${price:.2f} | P&L: {pnl_str} {pct_str}")

# Summary stats
cur.execute("""
    SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN action='BUY' THEN 1 ELSE 0 END) as buys,
        SUM(CASE WHEN action='SELL' THEN 1 ELSE 0 END) as sells,
        SUM(CASE WHEN action='SELL' AND pnl > 0 THEN 1 ELSE 0 END) as wins,
        COALESCE(SUM(pnl), 0) as total_pnl
    FROM trades_history
    WHERE DATE(trade_date) = '2026-01-16'
""")

result = cur.fetchone()
total_trades, buys_count, sells_count, wins, total_pnl = result
win_rate = (wins / sells_count * 100) if sells_count > 0 else 0

print(f"\n{'='*80}")
print("SUMMARY:")
print(f"  Total Trades: {total_trades}")
print(f"  Buys: {buys_count} | Sells: {sells_count}")
print(f"  Win Rate: {wins}/{sells_count} ({win_rate:.1f}%)")
print(f"  Total Realized P&L: ${total_pnl:.2f}")

# Get open positions
cur.execute("""
    SELECT 
        ticker,
        quantity,
        entry_price,
        current_price,
        unrealized_pnl,
        TO_CHAR(entry_date, 'HH12:MI AM') as entry_time
    FROM positions
    WHERE quantity > 0
    ORDER BY ticker
""")

positions = cur.fetchall()

if positions:
    print(f"\nOPEN POSITIONS: {len(positions)}")
    total_unrealized = 0
    for pos in positions:
        ticker, qty, entry, current, unrealized, entry_time = pos
        status = "🟢" if unrealized > 0 else "🔴" if unrealized < 0 else "⚪"
        print(f"  {status} {ticker}: {qty:.4f} shares @ ${entry:.2f} → ${current:.2f} | Unrealized: ${unrealized:.2f}")
        total_unrealized += unrealized
    print(f"\n  Total Unrealized P&L: ${total_unrealized:.2f}")
    print(f"  Net P&L (Realized + Unrealized): ${float(total_pnl) + total_unrealized:.2f}")
else:
    print(f"\nOPEN POSITIONS: 0 (All positions closed)")

print("="*80 + "\n")

conn.close()
