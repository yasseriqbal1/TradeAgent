"""Get all trades from today"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)

cur = conn.cursor()
cur.execute("""
    SELECT ticker, action, shares, price, total_value, pnl, pnl_pct, notes, trade_date 
    FROM trades_history 
    WHERE DATE(trade_date) = '2026-01-15' 
    ORDER BY trade_date
""")

rows = cur.fetchall()
print(f"\n{'='*80}")
print(f"COMPLETE DAY TRADES - January 15, 2026")
print(f"{'='*80}\n")
print(f"Total trades today: {len(rows)}\n")

buys = [r for r in rows if r[1] == 'BUY']
sells = [r for r in rows if r[1] == 'SELL']

print(f"BUYS: {len(buys)}")
for r in buys:
    time = r[8].strftime('%I:%M %p')
    print(f"  {time}: {r[0]} - {r[2]:.4f} shares @ ${r[3]:.2f} = ${r[4]:.2f}")
    
print(f"\nSELLS: {len(sells)}")
total_pnl = 0
wins = 0
for r in sells:
    time = r[8].strftime('%I:%M %p')
    pnl = r[5] if r[5] else 0
    pnl_pct = r[6] if r[6] else 0
    total_pnl += pnl
    if pnl > 0:
        wins += 1
    emoji = "🟢" if pnl > 0 else "🔴"
    print(f"  {emoji} {time}: {r[0]} - {r[2]:.4f} shares @ ${r[3]:.2f} | P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")

print(f"\n{'='*80}")
print(f"SUMMARY:")
print(f"  Total Trades: {len(rows)}")
print(f"  Buys: {len(buys)} | Sells: {len(sells)}")
print(f"  Win Rate: {wins}/{len(sells)} ({wins/len(sells)*100:.1f}%)")
print(f"  Total Realized P&L: ${total_pnl:.2f}")
print(f"{'='*80}\n")

cur.close()
conn.close()
