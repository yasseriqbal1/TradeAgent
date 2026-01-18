import psycopg2

conn = psycopg2.connect(
    dbname='tradeagent',
    user='postgres',
    password='yasser',
    host='localhost'
)

cur = conn.cursor()

# Get MU's correct quantity from trades_history (most recent BUY)
cur.execute("""
    SELECT shares, price, trade_date
    FROM trades_history
    WHERE ticker='MU' AND action='BUY' AND DATE(trade_date) = '2026-01-15'
    ORDER BY trade_date DESC
    LIMIT 1
""")

mu_data = cur.fetchone()
if mu_data:
    shares = mu_data[0]
    price = mu_data[1]
    trade_date = mu_data[2]
    
    print(f"\nMU Last BUY:")
    print(f"  Date: {trade_date}")
    print(f"  Shares: {shares}")
    print(f"  Price: ${price}")
    
    # Update MU position
    cur.execute("""
        UPDATE positions 
        SET quantity = %s
        WHERE ticker = 'MU' AND quantity = 0
    """, (shares,))
    conn.commit()
    
    print(f"\n✅ Updated MU position to {shares} shares")
else:
    print("\n❌ No MU BUY trade found")

# Verify all positions
cur.execute("SELECT ticker, quantity, entry_price FROM positions ORDER BY ticker")
positions = cur.fetchall()
print(f"\n{'='*80}")
print(f"ALL POSITIONS AFTER FIX:")
print(f"{'='*80}")
for row in positions:
    print(f"  {row[0]}: {row[1]} shares @ ${row[2]:.4f}")
print(f"{'='*80}\n")

conn.close()
