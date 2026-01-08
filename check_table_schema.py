import psycopg2
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

# Check table schema
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'positions' 
    ORDER BY ordinal_position
""")
cols = cur.fetchall()
print('Columns in positions table:')
for col in cols:
    print(f"  - {col[0]}")

print("\n" + "=" * 80)

# Get all data from positions table
cur.execute("SELECT * FROM positions WHERE exit_triggered = FALSE ORDER BY entry_time DESC")
rows = cur.fetchall()

print(f"\nTotal open positions: {len(rows)}")
if rows:
    print("\nPosition details:")
    for row in rows:
        print(row)

conn.close()
