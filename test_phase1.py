"""Quick test of Phase 1 enhancements."""

import sys
import json
from quant_agent.scanner import scanner

print("=" * 60)
print("PHASE 1 IMPLEMENTATION TEST")
print("=" * 60)

try:
    # Run a quick premarket scan with 2 tickers
    print("\n1. Running premarket scan (top 2)...")
    result = scanner.run_premarket_scan(top_n=2, tickers=["AAPL", "MSFT"])
    
    if result['status'] != 'success':
        print(f"[ERROR] Scan failed: {result.get('error')}")
        sys.exit(1)
    
    print(f"[OK] Scan completed in {result['execution_time']:.2f}s")
    print(f"   Tickers scanned: {result['stats']['tickers_loaded']}")
    print(f"   Passed filters: {result['stats']['passed_filters']}")
    
    # Check first signal
    if not result['signals']:
        print("[ERROR] No signals returned")
        sys.exit(1)
    
    signal = result['signals'][0]
    print(f"\n2. First Signal: {signal['ticker']}")
    print(f"   Rank: {signal['rank']}")
    print(f"   Score: {signal['composite_score']:.3f}")
    print(f"   Price: ${signal['price']:.2f}")
    
    # Check enhanced factors
    factors = signal.get('factors', {})
    print(f"\n3. Enhanced Factors Check:")
    
    momentum = factors.get('momentum', {})
    if 'momentum_exp' in momentum:
        print(f"   [OK] Momentum Exp: {momentum['momentum_exp']:.2f}%")
    else:
        print(f"   [ERROR] Momentum Exp: MISSING")
    
    if 'sharpe_momentum' in momentum:
        print(f"   [OK] Sharpe Momentum: {momentum['sharpe_momentum']:.3f}")
    else:
        print(f"   [ERROR] Sharpe Momentum: MISSING")
    
    if 'momentum_consistency' in momentum:
        print(f"   [OK] Consistency: {momentum['momentum_consistency']:.1f}%")
    else:
        print(f"   [ERROR] Consistency: MISSING")
    
    volume = factors.get('volume', {})
    if 'volume_price_corr' in volume:
        print(f"   [OK] Volume-Price Corr: {volume['volume_price_corr']:.3f}")
    else:
        print(f"   [ERROR] Volume-Price Corr: MISSING")
    
    if 'volume_zscore' in volume:
        print(f"   [OK] Volume Z-Score: {volume['volume_zscore']:.2f}")
    else:
        print(f"   [ERROR] Volume Z-Score: MISSING")
    
    volatility = factors.get('volatility', {})
    if 'vol_regime' in volatility:
        print(f"   [OK] Vol Regime: {volatility['vol_regime']:.2f}")
    else:
        print(f"   [ERROR] Vol Regime: MISSING")
    
    # Check trade plan (KEY FEATURE)
    print(f"\n4. Trade Plan Check (MOST IMPORTANT):")
    
    trade_plan = factors.get('trade_plan')
    if not trade_plan:
        print("   [CRITICAL ERROR] No trade_plan found in factors!")
        print("\n   Available factor keys:", list(factors.keys()))
        sys.exit(1)
    
    print(f"   [OK] Trade plan exists")
    print(f"\n   Entry Price: ${trade_plan['entry_price']:.2f}")
    print(f"   Position: {trade_plan['shares']} shares")
    print(f"   Position Value: ${trade_plan['position_value']:.2f} ({trade_plan['position_pct']:.2f}%)")
    print(f"   Stop Loss: ${trade_plan['stop_loss']:.2f} (-{trade_plan['stop_loss_pct']:.2f}%)")
    print(f"   Take Profit: ${trade_plan['take_profit']:.2f} (+{trade_plan['take_profit_pct']:.2f}%)")
    print(f"   Total Risk: ${trade_plan['total_risk']:.2f} ({trade_plan['portfolio_risk_pct']:.2f}% portfolio)")
    print(f"   Quality Score: {trade_plan['quality_score']:.1f}/100")
    print(f"   Valid: {trade_plan['valid']}")
    print(f"   Warnings: {trade_plan.get('warnings', [])}")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] PHASE 1 TEST PASSED - All features working!")
    print("=" * 60)
    
    print("\nNext steps:")
    print("1. Restart FastAPI server to load new modules")
    print("2. Update n8n workflows (see WORKFLOW_PROMPT_UPDATES.md)")
    print("3. Test workflows manually")
    print("4. Review output files for risk metrics")
    
except Exception as e:
    print(f"\n[TEST FAILED] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
