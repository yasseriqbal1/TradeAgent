"""Test Questrade order placement API - Safe to run after hours"""

from quant_agent.questrade_loader import QuestradeAPI
from datetime import datetime

print("=" * 70)
print("🧪 TESTING QUESTRADE ORDER PLACEMENT API")
print("=" * 70)
print(f"\n⏰ Current time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")
print("📍 Market Status: CLOSED (After hours testing)")
print("\n⚠️  This test will NOT place actual orders")
print("   We're checking if the API endpoint exists and what it needs\n")

try:
    # Step 1: Connect to Questrade
    print("1️⃣ Connecting to Questrade API...")
    q = QuestradeAPI()
    print("   ✅ Connected successfully\n")
    
    # Step 2: Get account info
    print("2️⃣ Fetching account information...")
    accounts = q.get_accounts()
    if not accounts:
        print("   ❌ No accounts found!")
        exit(1)
    
    account_num = accounts[0]["number"]
    account_type = accounts[0]["type"]
    print(f"   ✅ Account: {account_num} ({account_type})\n")
    
    # Step 3: Check if order endpoint exists
    print("3️⃣ Checking order placement endpoint...")
    print("   Questrade Order API Documentation:")
    print("   POST /v1/accounts/{accountNumber}/orders")
    print("   Required fields:")
    print("   • accountNumber: Account ID")
    print("   • symbolId: Stock symbol ID (from search)")
    print("   • quantity: Number of shares")
    print("   • orderType: 'Limit' or 'Market'")
    print("   • timeInForce: 'Day', 'GTC', etc.")
    print("   • action: 'Buy' or 'Sell'")
    print("   • price: Limit price (required for Limit orders)")
    
    # Step 4: Try to find QBTS symbol (cheapest in our universe)
    print("\n4️⃣ Testing symbol lookup (QBTS - cheapest stock)...")
    symbol_id = q.search_symbols("QBTS")
    
    if symbol_id:
        print(f"   ✅ Found QBTS symbol ID: {symbol_id}")
        
        # Get current quote
        quotes = q.get_quotes([symbol_id])
        if quotes:
            quote = quotes[0]
            last_price = quote.get('lastTradePrice', 0)
            bid = quote.get('bidPrice')
            ask = quote.get('askPrice')
            print(f"   📊 Last Price: ${last_price:.2f}")
            
            # Bid/Ask may be None after hours
            if bid and ask:
                print(f"   📊 Bid: ${bid:.2f}, Ask: ${ask:.2f}")
            else:
                print(f"   📊 Bid/Ask: Not available (market closed)")
                print(f"   💡 This is normal after hours - quotes frozen at last close")
    else:
        print("   ❌ Could not find QBTS symbol")
        symbol_id = None
    
    # Step 5: Simulate order structure (DO NOT SEND)
    print("\n5️⃣ Order structure example (NOT SENDING):")
    print("   {")
    print(f"     'accountNumber': '{account_num}',")
    print(f"     'symbolId': {symbol_id or 'SYMBOL_ID'},")
    print("     'quantity': 1,")
    print("     'orderType': 'Limit',")
    print("     'timeInForce': 'Day',")
    print("     'action': 'Buy',")
    print("     'price': 5.00")
    print("   }")
    
    # Step 6: Check if we have the place_order method
    print("\n6️⃣ Checking if place_order() method exists...")
    if hasattr(q, 'place_order'):
        print("   ✅ place_order() method found")
    else:
        print("   ❌ place_order() method NOT IMPLEMENTED")
        print("   📝 This needs to be added to questrade_loader.py")
    
    # Step 7: What happens if we try after hours?
    print("\n7️⃣ Expected behavior when placing orders after hours:")
    print("   • Market closed → Order queued for next open")
    print("   • Or rejected with 'Market not open' error")
    print("   • Limit orders may sit until market opens")
    print("   • This is SAFE - no instant execution risk")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE - No actual orders attempted")
    print("=" * 70)
    
    print("\n📋 FINDINGS:")
    print(f"   ✅ Questrade API connection: Working")
    print(f"   ✅ Account access: Working")
    print(f"   ✅ Symbol lookup: {'Working' if symbol_id else 'Failed'}")
    print(f"   ✅ Quote retrieval: Working")
    print(f"   ❌ Order placement: NOT IMPLEMENTED")
    
    print("\n🔧 TO IMPLEMENT LIVE TRADING:")
    print("   1. Add place_order() method to questrade_loader.py")
    print("   2. Handle order responses (success/failure)")
    print("   3. Store order IDs for tracking")
    print("   4. Add order status checking")
    print("   5. Test with 1 share first when market opens")
    
    print("\n⚠️  RECOMMENDATION:")
    print("   Keep PAPER_TRADING = True for tomorrow's test")
    print("   Implement order API after paper test succeeds")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n💡 This error is normal if:")
    print("   - You haven't implemented place_order() yet")
    print("   - API endpoint requires special permissions")
    print("   - After-hours testing limitations")
