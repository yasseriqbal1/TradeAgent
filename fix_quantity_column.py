import psycopg2

print("\n" + "="*80)
print("FIXING POSITIONS TABLE - QUANTITY COLUMN TYPE")
print("="*80)

conn = psycopg2.connect(
    dbname='tradeagent',
    user='postgres',
    password='yasser',
    host='localhost'
)

cur = conn.cursor()

# Step 1: Backup current positions
print("\n📋 Step 1: Backing up current positions...")
cur.execute("SELECT ticker, quantity, entry_price FROM positions")
backup = cur.fetchall()
print(f"   Backed up {len(backup)} positions")
for row in backup:
    print(f"   - {row[0]}: {row[1]} shares @ ${row[2]}")

# Step 2: Alter column type
print("\n🔧 Step 2: Altering quantity column from INTEGER to DOUBLE PRECISION...")
try:
    cur.execute("""
        ALTER TABLE positions 
        ALTER COLUMN quantity TYPE DOUBLE PRECISION;
    """)
    conn.commit()
    print("   ✅ Column type changed successfully!")
except Exception as e:
    print(f"   ❌ Error: {e}")
    conn.rollback()

# Step 3: Fix SLB position (set correct quantity from trades_history)
print("\n🔧 Step 3: Fixing SLB position with correct fractional shares...")
try:
    cur.execute("""
        UPDATE positions 
        SET quantity = 0.29253765
        WHERE ticker = 'SLB' AND quantity = 0
    """)
    conn.commit()
    rows_updated = cur.rowcount
    print(f"   ✅ Updated {rows_updated} SLB position(s)")
except Exception as e:
    print(f"   ❌ Error: {e}")
    conn.rollback()

# Step 4: Verify fix
print("\n✅ Step 4: Verifying fix...")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='positions' AND column_name='quantity'")
result = cur.fetchone()
print(f"   Column 'quantity' is now: {result[1]}")

cur.execute("SELECT ticker, quantity, entry_price FROM positions")
positions = cur.fetchall()
print(f"\n📊 Current positions after fix:")
for row in positions:
    print(f"   - {row[0]}: {row[1]} shares @ ${row[2]}")

print("\n" + "="*80)
print("✅ FIX COMPLETE!")
print("="*80 + "\n")

conn.close()
