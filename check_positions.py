import psycopg2
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'tradeagent'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '')
)
cur = conn.cursor()

# Get all open positions
cur.execute("""
    SELECT ticker, entry_price, entry_date, quantity, 
           stop_loss, take_profit, current_price, 
           unrealized_pnl, unrealized_pnl_pct
    FROM positions 
    WHERE exit_triggered = FALSE 
    ORDER BY entry_date DESC
""")

rows = cur.fetchall()

print("=" * 130)
print("CURRENT OPEN POSITIONS")
print("=" * 130)

if not rows:
    print("No open positions found.")
else:
    for row in rows:
        ticker, entry_price, entry_date, quantity, stop_loss, take_profit, current_price, pnl, pnl_pct = row
        print(f"\nSymbol: {ticker}")
        print(f"  Entry Price:    ${entry_price:.2f}")
        print(f"  Entry Date:     {entry_date}")
        print(f"  Quantity:       {quantity:.4f}")
        print(f"  Stop Loss:      ${stop_loss:.2f} ({((stop_loss - entry_price) / entry_price * 100):.2f}%)")
        print(f"  Take Profit:    ${take_profit:.2f} ({((take_profit - entry_price) / entry_price * 100):.2f}%)")
        print(f"  Current Price:  ${current_price:.2f}" if current_price else "  Current Price:  N/A")
        print(f"  Unrealized P&L: ${pnl:.2f} ({pnl_pct:.2f}%)" if pnl else "  Unrealized P&L: N/A")

conn.close()
