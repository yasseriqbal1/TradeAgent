"""
Create live trading tables in the database.
Reads the migration SQL file and executes it.
"""
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_tables():
    """Create live trading tables from migration file."""
    
    # Get database connection details
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'tradeagent')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD')
    
    print("=" * 60)
    print("Creating Live Trading Tables")
    print("=" * 60)
    print(f"\n📌 Database: {db_name}")
    
    # Read migration file
    migration_file = 'migrations/001_add_live_trading_tables.sql'
    print(f"\n📌 Reading migration file: {migration_file}")
    
    try:
        with open(migration_file, 'r') as f:
            sql = f.read()
        print("✅ Migration file loaded")
    except FileNotFoundError:
        print(f"❌ Migration file not found: {migration_file}")
        return False
    
    # Connect and execute
    try:
        print(f"\n📌 Connecting to database...")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        conn.autocommit = False  # Use transactions
        cur = conn.cursor()
        
        print("✅ Connected")
        print(f"\n📌 Executing migration...")
        
        # Execute the migration SQL
        cur.execute(sql)
        
        print("✅ SQL executed")
        print(f"\n📌 Committing transaction...")
        
        # Commit the transaction
        conn.commit()
        
        print("✅ Transaction committed")
        
        # Verify tables were created
        print(f"\n📌 Verifying tables...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema='public' 
            AND table_name IN ('live_signals', 'orders', 'positions', 'live_trades', 'risk_events')
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        
        print("\n" + "=" * 60)
        print("Tables Created")
        print("=" * 60)
        
        expected_tables = ['live_signals', 'live_trades', 'orders', 'positions', 'risk_events']
        
        for table in expected_tables:
            if table in tables:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} - FAILED")
        
        if len(tables) == 5:
            print("\n✅ All 5 live trading tables created successfully!")
            print("\n" + "=" * 60)
            print("Next Steps")
            print("=" * 60)
            print("\n1. Test database operations:")
            print("   python test_database.py")
            print("\n2. Run end-to-end integration test")
            print("\n3. Configure alerts in config/live_trading.yaml")
            print("\n4. Start paper trading!")
        else:
            print(f"\n⚠️  Only {len(tables)}/5 tables created")
        
        cur.close()
        conn.close()
        
        return len(tables) == 5
        
    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        if conn:
            conn.rollback()
            print("   Transaction rolled back")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = create_tables()
    
    if success:
        print("\n🎉 Database setup complete!")
    else:
        print("\n❌ Database setup failed")
