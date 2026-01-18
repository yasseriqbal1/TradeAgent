import psycopg2

conn = psycopg2.connect(
    dbname='tradeagent',
    user='postgres',
    password='yasser',
    host='localhost'
)

cur = conn.cursor()
cur.execute("""
    SELECT ticker, quantity, entry_price, entry_date, stop_loss, take_profit 
    FROM positions 
    WHERE ticker='SLB'
""")

result = cur.fetchall()
print(f"\nSLB Position in Database:")
print(f"{'='*80}")
if result:
    for row in result:
        print(f"Ticker: {row[0]}")
        print(f"Quantity: {row[1]}")
        print(f"Entry Price: ${row[2]}")
        print(f"Entry Time: {row[3]}")
        print(f"Stop Loss: ${row[4]}")
        print(f"Take Profit: ${row[5]}")
else:
    print("No SLB position found in database")
print(f"{'='*80}\n")

# Check trades_history for SLB
cur.execute("""
    SELECT trade_date, ticker, action, shares, price, notes
    FROM trades_history 
    WHERE ticker='SLB' AND DATE(trade_date) = '2026-01-15'
    ORDER BY trade_date
""")

trades = cur.fetchall()
print(f"\nSLB Trades on January 15:")
print(f"{'='*80}")
if trades:
    for trade in trades:
        print(f"{trade[0]} | {trade[2]} | {trade[3]} shares @ ${trade[4]} | {trade[5]}")
else:
    print("No SLB trades found for January 15")
print(f"{'='*80}\n")

conn.close()
