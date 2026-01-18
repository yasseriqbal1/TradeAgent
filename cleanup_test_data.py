"""Clean up test data from trades_history table"""
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
cur.execute("DELETE FROM trades_history WHERE ticker = 'TEST'")
conn.commit()
print(f"✅ Deleted {cur.rowcount} test trades")

cur.execute('SELECT COUNT(*) FROM trades_history')
print(f"Remaining trades in database: {cur.fetchone()[0]}")

cur.close()
conn.close()
print("✅ Database cleaned")
