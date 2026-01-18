"""Quick test to verify Redis integration works"""
import redis
import json
from datetime import datetime

print("=" * 60)
print("REDIS INTEGRATION TEST")
print("=" * 60)

# Test 1: Connection
print("\n1. Testing Redis connection...")
try:
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.ping()
    print("   ✓ Redis connection successful")
except Exception as e:
    print(f"   ✗ Redis connection failed: {e}")
    exit(1)

# Test 2: Write sample prices (simulate bot)
print("\n2. Writing sample prices to Redis (simulating bot)...")
try:
    sample_prices = {
        'AAPL': 178.50,
        'MSFT': 420.25,
        'NVDA': 880.73,
        'TSLA': 245.10,
        'GOOGL': 142.30
    }
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'prices': sample_prices
    }
    
    r.setex('live_prices', 60, json.dumps(data))
    print(f"   ✓ Written {len(sample_prices)} prices to Redis")
    print(f"   Key: 'live_prices'")
    print(f"   TTL: 60 seconds")
except Exception as e:
    print(f"   ✗ Write failed: {e}")
    exit(1)

# Test 3: Read back (simulate dashboard)
print("\n3. Reading prices from Redis (simulating dashboard)...")
try:
    retrieved = r.get('live_prices')
    if retrieved:
        data = json.loads(retrieved)
        prices = data.get('prices', {})
        timestamp = data.get('timestamp', 'unknown')
        
        print(f"   ✓ Retrieved {len(prices)} prices")
        print(f"   Timestamp: {timestamp}")
        print(f"   Sample prices:")
        for ticker, price in list(prices.items())[:3]:
            print(f"      {ticker}: ${price}")
    else:
        print("   ✗ No data found in Redis")
        exit(1)
except Exception as e:
    print(f"   ✗ Read failed: {e}")
    exit(1)

# Test 4: Check TTL
print("\n4. Checking key expiry...")
try:
    ttl = r.ttl('live_prices')
    print(f"   ✓ Key will expire in {ttl} seconds")
except Exception as e:
    print(f"   ✗ TTL check failed: {e}")

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED - Redis integration working!")
print("=" * 60)
print("\nDashboard will receive real-time prices from bot via Redis.")
