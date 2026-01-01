"""
Check what tables exist in the database and compare with required tables.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Required tables for live trading (Phase 3A)
REQUIRED_TABLES = {
    'live_signals',
    'orders',
    'positions',
    'live_trades',
    'risk_events'
}

# Expected backtest tables (from Phase 1 & 2)
BACKTEST_TABLES = {
    'backtest_runs',
    'backtest_trades',
    'daily_returns'
}

def check_tables():
    """Check what tables exist in the database."""
    
    # Get database connection details from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'tradeagent')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD')
    
    print("=" * 60)
    print("Database Table Check")
    print("=" * 60)
    print(f"\n📌 Connecting to database: {db_name}")
    print(f"   Host: {db_host}:{db_port}")
    print(f"   User: {db_user}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all tables in public schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema='public' 
            ORDER BY table_name
        """)
        
        existing_tables = {row['table_name'] for row in cur.fetchall()}
        
        print(f"\n✅ Connected successfully")
        print(f"\n📊 Tables found: {len(existing_tables)}")
        
        if existing_tables:
            print("\n" + "=" * 60)
            print("Existing Tables")
            print("=" * 60)
            for table in sorted(existing_tables):
                print(f"  ✓ {table}")
        
        # Check for Phase 3A live trading tables
        print("\n" + "=" * 60)
        print("Phase 3A Live Trading Tables Status")
        print("=" * 60)
        
        missing_live_tables = REQUIRED_TABLES - existing_tables
        present_live_tables = REQUIRED_TABLES & existing_tables
        
        if present_live_tables:
            print("\n✅ Present:")
            for table in sorted(present_live_tables):
                print(f"  ✓ {table}")
        
        if missing_live_tables:
            print("\n❌ Missing:")
            for table in sorted(missing_live_tables):
                print(f"  ✗ {table}")
        else:
            print("\n✅ All live trading tables present!")
        
        # Check for backtest tables
        print("\n" + "=" * 60)
        print("Phase 1 & 2 Backtest Tables Status")
        print("=" * 60)
        
        missing_backtest_tables = BACKTEST_TABLES - existing_tables
        present_backtest_tables = BACKTEST_TABLES & existing_tables
        
        if present_backtest_tables:
            print("\n✅ Present:")
            for table in sorted(present_backtest_tables):
                print(f"  ✓ {table}")
        
        if missing_backtest_tables:
            print("\n⚠️  Missing (optional - only needed for backtesting):")
            for table in sorted(missing_backtest_tables):
                print(f"  ✗ {table}")
        
        # Recommendations
        print("\n" + "=" * 60)
        print("Recommendations")
        print("=" * 60)
        
        if missing_live_tables:
            print("\n⚠️  Action Required:")
            print("  Phase 3A live trading tables are missing.")
            print("  Run the migration to create them:")
            print("  psql -d tradeagent -f migrations/001_add_live_trading_tables.sql")
            print("\n  Or run the full schema:")
            print("  psql -d tradeagent -f schema.sql")
        else:
            print("\n✅ Phase 3A tables ready!")
            print("  All live trading tables are present.")
            print("  System is ready for paper trading.")
        
        if missing_backtest_tables:
            print("\nℹ️  Note:")
            print("  Backtest tables are optional and only needed")
            print("  if you want to run backtests (Phase 1 & 2).")
        
        cur.close()
        conn.close()
        
        return {
            'existing_tables': existing_tables,
            'missing_live_tables': missing_live_tables,
            'missing_backtest_tables': missing_backtest_tables
        }
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check PostgreSQL is running")
        print("  2. Verify database 'tradeagent' exists")
        print("  3. Check credentials in .env file")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None

if __name__ == "__main__":
    result = check_tables()
    
    if result and result['missing_live_tables']:
        print("\n" + "=" * 60)
        print("Next Step: Create Missing Tables")
        print("=" * 60)
        print("\nWould you like to create the missing tables now? (y/n)")
