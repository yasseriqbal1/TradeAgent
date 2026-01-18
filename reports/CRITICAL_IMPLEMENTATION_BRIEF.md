# Critical Trading System Additions - Implementation Brief

You are helping me build a Python-based automated intraday trading system TradeAgent that will run with REAL CAPITAL.

## YOUR PRIMARY OBJECTIVE

Prevent catastrophic capital loss through simple, robust code additions. Every line of code you write could save or cost me thousands of dollars.

## CRITICAL RULES FOR YOU

1. **NO over-engineering** - Simple, readable, fail-safe code only
2. **NO complex algorithms** - If it needs a PhD to understand, don't write it
3. **NO "nice to have" features** - Only capital-preservation essentials
4. **Every addition must have a clear "prevents X disaster" justification**
5. **Prioritize execution safety over optimization**

---

## CRITICAL ADDITIONS NEEDED (In Priority Order)

### 1. PER-TRADE POSITION SIZE LIMIT

**Status:** MISSING (CRITICAL RISK)

**Why we need it:**

- Currently no limit on single position size
- One bad trade can blow through entire 8% daily loss limit
- In live markets, fat-finger errors or bad fills can create oversized positions
- Without this, one position = entire portfolio at risk

**What to implement:**

```python
MAX_POSITION_SIZE_PCT = 0.02  # 2% of portfolio per trade max
```

**Implementation requirements:**

- Calculate max dollar amount per position = portfolio_value \* 0.02
- Cap share quantity before order submission
- Log warning if order would exceed limit (don't just silently cap)
- Make this check happen AFTER all entry signals, BEFORE order placement

**Prevents:** Single position wiping out 5-10% of capital in minutes

---

### 2. TIME-OF-DAY TRADING BLACKOUT

**Status:** MISSING (HIGH RISK)

**Why we need it:**

- First 15 minutes (9:30-9:45 AM ET) has widest spreads, fake breakouts, stop hunts
- Last 15 minutes (3:45-4:00 PM ET) has erratic closes, MOC order imbalances
- These periods generate the most false signals and worst execution prices
- Professional traders avoid these windows for good reason

**What to implement:**

```python
TRADING_START_TIME = time(9, 35)   # Start trading at 9:45 AM ET
TRADING_END_TIME = time(15, 55)    # Stop new entries at 3:45 PM ET
```

**Implementation requirements:**

- Check current time (in ET timezone) before EVERY entry decision
- Block new entries outside window (exits can happen anytime)
- Simple boolean: `is_trading_hours()` function
- No complicated logic - just hard start/stop times

**Prevents:** Death by 1000 cuts in chaotic open/close periods, expensive slippage

---

### 3. EARNINGS & SCHEDULED NEWS BLACKLIST

**Status:** MISSING (CRITICAL RISK)

**Why we need it:**

- Stocks gap 10-20% on earnings regularly
- You will enter positions minutes before earnings and get destroyed
- No technical signal can predict earnings surprises
- Halts, FDA approvals, FOMC - all create discontinuous price moves your stops can't handle

**What to implement (SIMPLE VERSION FIRST):**

```python
# Phase 1: Manual blacklist of known event times
FED_ANNOUNCEMENT_DATES = ['2026-01-11', '2026-03-31']  # Update quarterly
BLACKLIST_HOURS_BEFORE_FED = 2  # No trades 2 hours before FOMC

# Phase 2: Per-stock earnings check (integrate API later)
def is_earnings_today(symbol):
    # Check if earnings date = today
    # Return True if earnings within 24 hours
    pass
```

**Implementation requirements:**

- **START SIMPLE:** Hardcode known Fed dates, block trading those afternoons
- Add per-stock earnings check using your existing data provider API
- Block entries if earnings are today or tomorrow
- Don't try to predict or trade through news - just AVOID it

**Prevents:** Single 15% gap move destroying multiple days of profits, catastrophic overnight holds

---

### 4. ENHANCED CIRCUIT BREAKER - INTRADAY KILL SWITCH

**Status:** PARTIAL (needs improvement)

**Why we need it:**

- Current drawdown checks happen at entry/exit
- VIX can spike from 18 to 40 mid-session (Flash Crash, COVID crash)
- You need ability to STOP ALL TRADING when market structure breaks
- Existing positions need emergency exits when regime flips violently

**What to implement:**

```python
# Check EVERY LOOP, not just at entry
def check_emergency_conditions():
    current_vix = get_current_vix()
    current_spy_change = get_spy_percent_change_today()

    # Emergency halt conditions
    if current_vix > 40:  # VIX spike
        return "HALT_ALL"
    if current_spy_change < -3.0:  # SPY down 3%+ intraday
        return "HALT_ALL"
    if current_session_drawdown > 0.15:  # 15% drawdown
        return "CLOSE_ALL"

    return "NORMAL"
```

**Implementation requirements:**

- Run this check in your main loop (every 1-5 minutes)
- Three states: NORMAL, HALT_ALL (no new entries), CLOSE_ALL (exit everything)
- Log state changes prominently
- Manual override capability to force HALT_ALL

**Prevents:** Algorithm continuing to trade into market crash, compounding losses while you're away from keyboard

---

### 5. ORDER VALIDATION & SANITY CHECKS

**Status:** UNKNOWN (likely missing)

**Why we need it:**

- Broker APIs fail silently
- You can submit orders for 10,000 shares when you meant 100
- Network glitches cause duplicate orders
- Price data can be stale or wrong

**What to implement:**

```python
def validate_order_before_submission(symbol, quantity, price, side):
    """Last line of defense before order hits broker"""

    # Sanity checks
    if quantity <= 0:
        raise ValueError(f"Invalid quantity: {quantity}")

    if quantity * price > MAX_POSITION_SIZE:
        raise ValueError(f"Position size ${quantity * price} exceeds limit")

    current_price = get_current_price(symbol)
    price_deviation = abs(price - current_price) / current_price

    if price_deviation > 0.02:  # Price is 2%+ away from current
        raise ValueError(f"Order price {price} is stale vs current {current_price}")

    # Check for duplicate orders in last 60 seconds
    if check_recent_order_duplicate(symbol, side):
        raise ValueError(f"Duplicate order detected for {symbol}")

    return True
```

**Implementation requirements:**

- Run this immediately before `broker.submit_order()`
- Raise exceptions - don't silently skip
- Log every validation check
- Make limits configurable but conservative by default

**Prevents:** Fat finger errors, stale data trades, accidental 10x position sizes

---

### 6. POSITION & ORDER STATE RECONCILIATION

**Status:** PROBABLY MISSING (HIGH RISK)

**Why we need it:**

- Your code thinks position is 100 shares
- Broker says position is 200 shares
- Orders get partially filled
- Network drops during order submission
- Race conditions between entry/exit signals

**What to implement:**

```python
def reconcile_positions_with_broker():
    """Run every 5 minutes - make sure we match broker state"""

    our_positions = get_internal_position_tracker()
    broker_positions = broker.get_positions()

    mismatches = []
    for symbol in set(our_positions.keys()) | set(broker_positions.keys()):
        our_qty = our_positions.get(symbol, 0)
        broker_qty = broker_positions.get(symbol, 0)

        if our_qty != broker_qty:
            mismatches.append({
                'symbol': symbol,
                'our_qty': our_qty,
                'broker_qty': broker_qty,
                'difference': broker_qty - our_qty
            })

            # HALT TRADING on this symbol until resolved
            add_to_blacklist(symbol, reason="position_mismatch")

    if mismatches:
        send_alert(f"POSITION MISMATCH DETECTED: {mismatches}")

    return mismatches
```

**Implementation requirements:**

- Run in background thread every 5 minutes
- On mismatch: STOP trading that symbol immediately
- Alert you (email, SMS, Slack - whatever you monitor)
- Don't try to auto-fix - require manual intervention
- Log every reconciliation attempt

**Prevents:** Doubling positions, orphaned positions, order state corruption

---

## IMPLEMENTATION PRIORITY

**Week 1 - Before ANY live capital:**

1. Per-trade position size limit
2. Time-of-day blackout
3. Order validation checks

**Week 2 - Before scaling capital:** 4. Enhanced circuit breaker 5. Position reconciliation

**Week 3 - Before going full size:** 6. Earnings blacklist (at least Fed dates + manual earnings dates)

---

## TESTING REQUIREMENTS FOR EACH ADDITION

Before marking ANY of these as "done," you must:

1. **Write a test that FORCES the failure condition**
   - Example: Mock an order 10x too large and verify it's rejected
2. **Verify logging works**
   - Every rejection, every alert must be logged clearly
3. **Test the failure mode manually**

   - Unplug network during order submission
   - Send duplicate orders
   - Submit orders during blackout window

4. **Paper trade for 1 week minimum**
   - Watch for false positives (legitimate trades blocked)
   - Watch for false negatives (bad trades allowed through)

---

## CODE STYLE REQUIREMENTS

```python
# GOOD - Simple, obvious, fail-safe
if current_time < TRADING_START_TIME:
    logger.warning(f"Blocking entry: before trading hours ({current_time})")
    return False

# BAD - Clever, compact, fragile
return False if (t := datetime.now().time()) < time(9,45) else check_other_conditions()
```

**Rules:**

- Explicit > implicit
- Verbose logging > silent failures
- Hard limits > soft limits
- Fail loudly > fail silently
- Conservative defaults > aggressive optimization

---

## WHAT NOT TO DO

❌ **Don't add:** Machine learning, predictive models, optimization algorithms
❌ **Don't add:** Complex multi-factor scoring, Bayesian filters, Kalman filters  
❌ **Don't add:** Real-time Greeks calculations, options pricing, portfolio optimization
❌ **Don't add:** Websocket reconnection logic with exponential backoff (use library)
❌ **Don't add:** Custom logging frameworks (use stdlib logging)
❌ **Don't add:** Abstract factory patterns, dependency injection containers

✅ **Do add:** Simple if/else checks that prevent disaster
✅ **Do add:** Hardcoded limits that are easy to audit
✅ **Do add:** Loud alerts when something is wrong
✅ **Do add:** Comments explaining WHY each check exists

---

## WHEN YOU WRITE CODE FOR ME

1. **Start every function with a comment explaining what disaster it prevents**
2. **Use descriptive variable names** (`max_position_dollars` not `mp`)
3. **Add logging at every decision point**
4. **Raise exceptions for safety violations** (don't return False silently)
5. **Include a simple test case showing the failure mode**

---

## FINAL REMINDER

I am about to risk REAL MONEY with this code.

Every shortcut you take, every "TODO" you leave, every edge case you ignore could cost me thousands of dollars or worse.

When in doubt:

- **Block the trade**
- **Halt the system**
- **Alert the human**

It's better to miss 100 good trades than to take 1 catastrophic trade.

Now help me implement these additions. Start with #1 (Position Size Limit).
