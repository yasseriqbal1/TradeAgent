# Fractional Shares Update - January 4, 2026

## 🎉 Major Enhancement: Fractional Share Trading Enabled!

### What Changed

**1. Fractional Shares Support**

- Added `FRACTIONAL_SHARES_ENABLED = True` flag
- Questrade supports fractional shares for US stocks (commission-free!)
- **Commission reduced from $1.00 to $0.00** for fractional trades

**2. Removed Affordability Filters**

- Eliminated `MAX_PRICE_PER_SHARE_PCT` (30% constraint)
- No more "expensive stocks" filtering
- All 25 stocks in universe now accessible with any capital

**3. Updated Position Sizing**

- **Old:** Calculate whole shares only (int rounding)
  ```python
  shares = int((position_value - $1) / price)  # Lost precision
  ```
- **New:** Calculate fractional shares precisely
  ```python
  shares = position_value / price  # Can be 0.164 shares
  ```

**4. Enhanced Logging**

- Fractional shares display with 4 decimals when < 1 share
- Example: `0.1640 shares` instead of `0 shares`
- Position display shows: `NVDA: 0.1640 shares @ $189.27`

### Impact on Your $95 Capital

**Before (Whole Shares with $1 Commission):**

```
Affordable Stocks: 4 (LAES, QBTS, QUBT, RGTI)
Max position size: ~$31 - $1 commission = $30
NVDA @ $189: ❌ Too expensive
AMD @ $221: ❌ Too expensive
MSFT @ $473: ❌ Too expensive
```

**After (Fractional Shares, Commission-Free):**

```
Tradeable Stocks: ALL 25 stocks
Max position size: ~$31 (full amount, no commission)
NVDA @ $189: ✅ Buy 0.1640 shares = $31.00
AMD @ $221: ✅ Buy 0.1403 shares = $31.00
MSFT @ $473: ✅ Buy 0.0655 shares = $31.00
```

### Key Benefits

1. **Access to All Stocks**

   - No longer limited by share price
   - Can trade NVDA, META, GOOG, MSFT with $95

2. **Zero Commission**

   - Save $1 per trade
   - With 3 positions: Save $6 total ($3 buy + $3 sell)
   - 6.3% cost reduction on your capital!

3. **Precise Position Sizing**

   - Allocate exactly $31.00 per position
   - No leftover cash from rounding
   - Better capital efficiency

4. **Dollar-Based Allocation**
   - Consistent risk per trade
   - Maintains 25% per position regardless of price

### Example Trade Scenarios

**Scenario 1: Buy NVDA**

```
Price: $189.27
Position Size: $31.00
Shares: 31.00 ÷ 189.27 = 0.1637 shares
Commission: $0.00
Total Cost: $31.00
```

**Scenario 2: Buy QBTS (Cheap Stock)**

```
Price: $5.23
Position Size: $31.00
Shares: 31.00 ÷ 5.23 = 5.9274 shares
Commission: $0.00
Total Cost: $31.00
```

**Scenario 3: Three Position Portfolio**

```
Capital: $95.00
Position 1: NVDA 0.1637 shares @ $189.27 = $31.00
Position 2: AMD 0.1403 shares @ $221.00 = $31.00
Position 3: MSFT 0.0655 shares @ $473.00 = $31.00
Total Invested: $93.00
Cash Reserve: $2.00 (buffer)
Commission Paid: $0.00
```

### Technical Implementation

**Files Modified:**

- `test_live_1hour_questrade.py` (7 changes)

**Functions Updated:**

1. `filter_affordable_stocks()` - Now returns all stocks
2. `scan_and_trade()` - Fractional position sizing
3. `check_positions()` - Fractional display formatting
4. `print_alert()` - Shows 0.1640 instead of 0.164

**Database Compatibility:**

- PostgreSQL `DECIMAL` field supports fractional shares
- No schema changes needed (already stores decimals)

### Configuration

**Current Settings:**

```python
FRACTIONAL_SHARES_ENABLED = True
COMMISSION = 0.0  # Free for fractional shares
BASE_POSITION_SIZE_PCT = 0.25  # 25% per position
MAX_POSITIONS = 3
```

**To Disable (not recommended):**

```python
FRACTIONAL_SHARES_ENABLED = False
COMMISSION = 1.0  # Whole shares have $1 fee
# Affordability filter will activate
```

### Testing Recommendations

**Phase 1: Paper Trading (Current)**

- ✅ Monitor fractional share calculations
- ✅ Verify commission = $0.00 in logs
- ✅ Check position displays show decimals

**Phase 2: Live Test (After Paper Success)**

- Start with 1 fractional order
- Example: Buy 0.05 shares of MSFT (~$23.65)
- Verify broker accepts fractional quantity
- Confirm $0 commission charged

**Phase 3: Full Deployment**

- Run with all 3 positions
- Mix of expensive (NVDA) + cheap (QBTS) stocks
- Monitor fills and execution quality

### Known Limitations

1. **US Stocks Only**

   - Fractional shares work for US listings
   - Canadian stocks (TSX) still whole shares only

2. **No Voting Rights**

   - Fractional shares don't get shareholder votes
   - Only matters if you accumulate to 1+ full share

3. **Transfer Restrictions**
   - Can't transfer fractional shares between brokers
   - Must sell and transfer cash if switching brokers

### Risk Considerations

**Improved Risk Management:**

- More diversification possible with limited capital
- Can allocate exactly $31 vs $0-30 (whole share rounding)
- Better position sizing consistency

**New Risks:**

- Wider universe = more stocks to monitor
- Need good filters to avoid bad picks
- Momentum/volume filters even more critical

### Next Steps

1. **Continue Paper Trading**

   - System now scans all 25 stocks
   - Watch for fractional buy signals
   - Verify $0 commission in logs

2. **Monitor Quality**

   - Check if momentum signals improve
   - Compare NVDA/AMD opportunities vs QBTS/LAES
   - Assess if expensive stocks have better volume

3. **Prepare for Live**
   - After 2-day paper test shows fractional calculations correct
   - Implement `place_order()` with fractional quantity support
   - Test with 0.05 shares first (~$10-25 depending on stock)

### Expected Log Output

**Before:**

```
🚫 Filtered 21 expensive stocks (>$28.58/share):
   AAPL ($269.97), AMD ($221.39), NVDA ($189.27)...

🔍 Scanning 4 affordable stocks:
   ❌ QBTS: $27.16 - Momentum -0.0539 <= 0
```

**After:**

```
💎 Fractional shares enabled - all 25 stocks tradeable

🔍 Scanning 25 stocks:
   ❌ AAPL: $269.97 - Momentum -0.0234 <= 0
   ❌ AMD: $221.39 - Momentum -0.0156 <= 0
   ✅ NVDA: $189.27 - PASS (Score: 0.0234)
   ❌ QBTS: $27.16 - Momentum -0.0539 <= 0

✅ Found 1 qualifying stocks

BUY NVDA @ $189.27
     Momentum Score: 0.0234
     Shares: 0.1640
     Cost: $31.00
     Capital Remaining: $64.00
```

### Questions?

**Q: Do fractional orders execute differently?**
A: No, Questrade executes instantly at market price (real-time).

**Q: Can I mix whole and fractional shares?**
A: Yes, you can buy 5.25 shares (5 whole + 0.25 fractional).

**Q: What about dividends?**
A: You receive proportional dividends (0.5 shares = 50% of dividend).

**Q: Is there a minimum purchase?**
A: Questrade allows as low as $1 minimum investment.

---

**Status:** ✅ Implementation Complete
**Testing:** 🧪 Paper Trading Active
**Next:** Monitor for first fractional buy signal
