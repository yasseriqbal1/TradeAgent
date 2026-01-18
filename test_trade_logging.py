"""Test script to verify trade logging functionality"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        load_dotenv()
        db_password = os.getenv('DB_PASSWORD', '')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_name = os.getenv('DB_NAME', 'tradeagent')
        db_user = os.getenv('DB_USER', 'postgres')
        
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def log_trade_to_db(ticker, action, shares, price, capital_before, total_positions, 
                    exit_reason=None, entry_price=None, hold_minutes=None, pnl=None, pnl_pct=None, notes=None):
    """Log every trade (buy/sell) to trades_history table"""
    conn = get_db_connection()
    if not conn:
        print("❌ No database connection")
        return False
    
    try:
        total_value = shares * price
        capital_after = capital_before - total_value if action == 'BUY' else capital_before + total_value
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trades_history 
                (ticker, action, shares, price, total_value, 
                 exit_reason, entry_price, hold_duration_minutes, pnl, pnl_pct,
                 capital_before, capital_after, total_positions, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ticker, action, shares, price, total_value,
                exit_reason, entry_price, hold_minutes, pnl, pnl_pct,
                capital_before, capital_after, total_positions, notes
            ))
            conn.commit()
        conn.close()
        print(f"✅ Trade logged: {action} {shares} {ticker} @ ${price}")
        return True
    except Exception as e:
        print(f"❌ Failed to log trade: {str(e)}")
        if conn:
            conn.close()
        return False

# Test 1: Log a BUY trade
print("\n=== TEST 1: Logging BUY trade ===")
result1 = log_trade_to_db(
    ticker='TEST',
    action='BUY',
    shares=1.0,
    price=100.0,
    capital_before=1000.0,
    total_positions=1,
    notes='Manual test - BUY'
)
print(f"Result: {result1}")

# Test 2: Log a SELL trade
print("\n=== TEST 2: Logging SELL trade ===")
result2 = log_trade_to_db(
    ticker='TEST',
    action='SELL',
    shares=1.0,
    price=105.0,
    capital_before=900.0,
    total_positions=0,
    exit_reason='take_profit',
    entry_price=100.0,
    hold_minutes=30,
    pnl=5.0,
    pnl_pct=5.0,
    notes='Manual test - SELL'
)
print(f"Result: {result2}")

# Verify database
print("\n=== Checking database ===")
conn = get_db_connection()
if conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as count FROM trades_history")
        count = cur.fetchone()['count']
        print(f"Total trades in database: {count}")
        
        cur.execute("SELECT ticker, action, shares, price, notes FROM trades_history ORDER BY trade_date DESC LIMIT 5")
        trades = cur.fetchall()
        print("\nRecent trades:")
        for trade in trades:
            print(f"  {trade['ticker']}: {trade['action']} {trade['shares']} @ ${trade['price']} - {trade['notes']}")
    conn.close()
