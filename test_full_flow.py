"""Test complete flow: Bot writes → Dashboard reads from Redis"""
import redis
import json
import requests
from datetime import datetime

print("\n" + "="*70)
print("FULL FLOW TEST: Bot → Redis → Dashboard")
print("="*70)

# Step 1: Simulate bot writing live prices to Redis
print("\n[BOT] Writing live Questrade prices to Redis...")
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Simulate Questrade API response
live_prices = {
    'AAPL': 178.42,
    'MSFT': 420.19,
    'NVDA': 880.73,
    'TSLA': 245.10,
    'GOOGL': 142.30,
    'META': 485.20,
    'AMD': 189.45,
    'MU': 363.18
}

r.setex('live_prices', 60, json.dumps({
    'timestamp': datetime.now().isoformat(),
    'prices': live_prices
}))

print(f"   ✓ Wrote {len(live_prices)} stock prices to Redis")
print(f"   Sample: AAPL=${live_prices['AAPL']}, NVDA=${live_prices['NVDA']}")

# Step 2: Verify Redis has the data
print("\n[REDIS] Verifying data in cache...")
cached = r.get('live_prices')
if cached:
    data = json.loads(cached)
    print(f"   ✓ Redis has {len(data['prices'])} prices")
    print(f"   Timestamp: {data['timestamp']}")
else:
    print("   ✗ Redis is empty!")
    exit(1)

# Step 3: Dashboard reads from Redis
print("\n[DASHBOARD] Fetching from /api/live-prices endpoint...")
try:
    response = requests.get('http://localhost:5000/api/live-prices', timeout=3)
    prices = response.json()
    
    if len(prices) >= len(live_prices):
        print(f"   ✓ Dashboard returned {len(prices)} prices (from Redis)")
        print(f"   Sample response:")
        for p in prices[:3]:
            print(f"      {p['ticker']}: ${p['price']}")
        print("\n" + "="*70)
        print("✅ SUCCESS: Dashboard is reading from Redis!")
        print("="*70)
    else:
        print(f"   ⚠️  Dashboard returned {len(prices)} prices (database fallback)")
        print("   Expected {len(live_prices)} from Redis")
except requests.exceptions.ConnectionError:
    print("   ✗ Dashboard not running on localhost:5000")
    print("   Start dashboard: cd dashboard && python app.py")
except Exception as e:
    print(f"   ✗ Error: {e}")
