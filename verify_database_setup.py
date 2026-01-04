"""
Database Setup Verification Script
Checks if PostgreSQL connection works and positions table exists
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import os
from dotenv import load_dotenv

# Load configuration from .env file
load_dotenv()
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'tradeagent')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

def test_connection():
    """Test PostgreSQL connection"""
    print("🔍 Testing PostgreSQL connection...")
    
    if not DB_PASSWORD:
        print("❌ DB_PASSWORD not found in .env file")
        print("\n💡 Fix:")
        print("   1. Ensure .env file exists in project root")
        print("   2. Add: DB_PASSWORD=your_password")
        return False
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("✅ Successfully connected to PostgreSQL!")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Fix:")
        print(f"   1. Check credentials in .env file")
        print(f"   2. Ensure PostgreSQL is running: Get-Service postgresql*")
        print(f"   3. Verify database exists: psql -U postgres -l")
        return False

def check_positions_table():
    """Check if positions table exists and show structure"""
    print("\n🔍 Checking positions table...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'positions'
                );
            """)
            exists = cur.fetchone()['exists']
            
            if exists:
                print("✅ Positions table exists!")
                
                # Show table structure
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'positions'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                
                print("\n📋 Table Structure:")
                print(f"   {'Column':<25} {'Type':<20} {'Nullable':<10}")
                print(f"   {'-'*25} {'-'*20} {'-'*10}")
                for col in columns:
                    print(f"   {col['column_name']:<25} {col['data_type']:<20} {col['is_nullable']:<10}")
                
                # Count existing positions
                cur.execute("SELECT COUNT(*) as count FROM positions WHERE exit_triggered = FALSE;")
                count = cur.fetchone()['count']
                print(f"\n📊 Current open positions: {count}")
                
                if count > 0:
                    cur.execute("""
                        SELECT ticker, quantity, entry_price, 
                               unrealized_pnl, unrealized_pnl_pct, updated_at
                        FROM positions 
                        WHERE exit_triggered = FALSE
                        ORDER BY updated_at DESC;
                    """)
                    positions = cur.fetchall()
                    print("\n🔹 Open Positions:")
                    for pos in positions:
                        print(f"   {pos['ticker']}: {pos['quantity']} shares @ ${pos['entry_price']:.2f}")
                        print(f"      P&L: ${pos['unrealized_pnl']:.2f} ({pos['unrealized_pnl_pct']:+.2f}%)")
                        print(f"      Updated: {pos['updated_at']}")
                
                conn.close()
                return True
            else:
                print("❌ Positions table does NOT exist!")
                print("\n💡 Fix: Run this SQL to create it:")
                print("""
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    quantity INT NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_date TIMESTAMP NOT NULL DEFAULT NOW(),
    current_price FLOAT NOT NULL,
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    max_hold_days INT NOT NULL,
    unrealized_pnl FLOAT DEFAULT 0,
    unrealized_pnl_pct FLOAT DEFAULT 0,
    position_value FLOAT,
    entry_order_id VARCHAR(50),
    stop_order_id VARCHAR(50),
    take_profit_order_id VARCHAR(50),
    signal_id VARCHAR(50),
    notes TEXT,
    exit_triggered BOOLEAN DEFAULT FALSE,
    exit_reason VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
                """)
                conn.close()
                return False
                
    except Exception as e:
        print(f"❌ Error checking table: {e}")
        return False

def test_insert_delete():
    """Test insert and delete operations"""
    print("\n🔍 Testing insert/delete operations...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        with conn.cursor() as cur:
            # Insert test position
            cur.execute("""
                INSERT INTO positions 
                (ticker, quantity, entry_price, entry_date, current_price,
                 stop_loss, take_profit, max_hold_days, position_value,
                 unrealized_pnl, unrealized_pnl_pct, updated_at)
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (ticker) DO NOTHING
                RETURNING id;
            """, ('TEST', 10, 100.0, 100.0, 85.0, 140.0, 30, 1000.0, 0.0, 0.0))
            
            result = cur.fetchone()
            if result:
                print("✅ Test insert successful!")
                
                # Delete test position
                cur.execute("DELETE FROM positions WHERE ticker = 'TEST';")
                print("✅ Test delete successful!")
                
                conn.commit()
            else:
                print("⚠️  Test ticker already exists (no insert)")
                conn.rollback()
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Operation test failed: {e}")
        return False

def main():
    """Run all checks"""
    print("=" * 70)
    print("PostgreSQL Database Setup Verification")
    print("=" * 70)
    
    # Test 1: Connection
    if not test_connection():
        print("\n❌ Setup incomplete - fix connection issues first")
        sys.exit(1)
    
    # Test 2: Table exists
    if not check_positions_table():
        print("\n❌ Setup incomplete - create positions table first")
        sys.exit(1)
    
    # Test 3: Insert/Delete
    if not test_insert_delete():
        print("\n⚠️  Operations test failed but table exists")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✅ ALL CHECKS PASSED - Database ready for live trading!")
    print("=" * 70)
    print("\n📝 Next steps:")
    print("   1. Run: python download_historical_data.py")
    print("   2. Run: python test_live_1hour_questrade.py")
    print("   3. Verify positions are saved to database")
    print("\n💡 Monitor positions: SELECT * FROM positions;")

if __name__ == "__main__":
    main()
