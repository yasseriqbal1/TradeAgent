"""
Clear all positions from database - Fresh start
Run this to delete old paper trade positions before starting with real balance
"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'trading_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT', '5432')
}

def clear_positions():
    """Delete all positions from database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Count current positions
        cur.execute("SELECT COUNT(*) FROM positions WHERE exit_triggered = FALSE")
        count = cur.fetchone()[0]
        
        print(f"📊 Found {count} open positions in database")
        
        if count == 0:
            print("✅ No positions to clear")
            conn.close()
            return
        
        # Show positions before deleting
        cur.execute("SELECT ticker, quantity, entry_price FROM positions WHERE exit_triggered = FALSE")
        positions = cur.fetchall()
        
        print("\n🗑️  Positions to be deleted:")
        for ticker, qty, entry in positions:
            print(f"   • {ticker}: {qty} shares @ ${entry:.2f}")
        
        # Confirm deletion
        response = input("\n⚠️  Delete all positions? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            # Delete all open positions
            cur.execute("DELETE FROM positions WHERE exit_triggered = FALSE")
            deleted = cur.rowcount
            conn.commit()
            print(f"\n✅ Deleted {deleted} positions")
            print("🎯 Database cleared - ready for fresh start!")
        else:
            print("\n❌ Cancelled - no positions deleted")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 70)
    print("🧹 CLEAR POSITIONS DATABASE")
    print("=" * 70)
    print("\nThis will delete all open positions from the database.")
    print("Use this to start fresh after paper trading.\n")
    
    clear_positions()
