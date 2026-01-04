"""Quick test to verify CAD to USD balance conversion."""

from quant_agent.questrade_loader import QuestradeAPI

print("🔍 Testing Questrade Balance & Currency Conversion\n")

try:
    # Initialize API
    print("1️⃣ Connecting to Questrade...")
    q = QuestradeAPI()
    print("   ✅ Connected\n")
    
    # Get accounts
    print("2️⃣ Fetching accounts...")
    accts = q.get_accounts()
    if not accts:
        print("   ❌ No accounts found!")
        exit(1)
    
    account_num = accts[0]["number"]
    account_type = accts[0]["type"]
    print(f"   ✅ Account: {account_num} ({account_type})\n")
    
    # Get balances
    print("3️⃣ Fetching balances...")
    bal = q.get_balances(account_num)
    
    if not bal:
        print("   ❌ Could not retrieve balances!")
        exit(1)
    
    # Extract values
    cash_cad = float(bal.get('cash', 0))
    equity_cad = float(bal.get('totalEquity', 0))
    buying_power_cad = float(bal.get('buyingPower', 0))
    
    # Convert to USD (1 CAD = 0.73 USD)
    USD_CAD_RATE = 0.73
    cash_usd = cash_cad * USD_CAD_RATE
    equity_usd = equity_cad * USD_CAD_RATE
    buying_power_usd = buying_power_cad * USD_CAD_RATE
    
    # Display results
    print("   ✅ Balances Retrieved\n")
    print("=" * 60)
    print("💵 ACCOUNT BALANCES")
    print("=" * 60)
    print(f"\n💰 Cash:")
    print(f"   CAD: ${cash_cad:,.2f}")
    print(f"   USD: ${cash_usd:,.2f}")
    print(f"\n📈 Total Equity:")
    print(f"   CAD: ${equity_cad:,.2f}")
    print(f"   USD: ${equity_usd:,.2f}")
    print(f"\n💪 Buying Power:")
    print(f"   CAD: ${buying_power_cad:,.2f}")
    print(f"   USD: ${buying_power_usd:,.2f}")
    print(f"\n🔄 Conversion Rate: 1 CAD = {USD_CAD_RATE} USD")
    print("=" * 60)
    
    # Verify expected values
    print("\n✅ VERIFICATION:")
    if 125 <= equity_cad <= 135:
        print(f"   ✅ CAD balance looks correct (~$130)")
    else:
        print(f"   ⚠️  Expected ~CAD $130, got CAD ${equity_cad:.2f}")
    
    if 90 <= equity_usd <= 100:
        print(f"   ✅ USD conversion looks correct (~$95)")
    else:
        print(f"   ⚠️  Expected ~USD $95, got USD ${equity_usd:.2f}")
    
    print(f"\n🎯 Trading capital will be: ${equity_usd:.2f} USD")
    print(f"🎯 Max position size: ${equity_usd / 3:.2f} each (3 positions)")
    print(f"🎯 Max affordable share price: ${equity_usd * 0.30:.2f}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
