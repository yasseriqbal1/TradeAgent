# TradeAgent Quantitative Framework Analysis

**Date:** December 29, 2025
**Focus:** Short-term Trading (1-5 days)

---

## Executive Summary

**Current Status:** ⚠️ **BASIC - NEEDS ENHANCEMENT**

Your system has a solid foundation but lacks sophistication for consistent short-term trading profits in 2025+ markets. The current approach is suitable for **screening** but not **execution-grade trading signals**.

**Risk Level:** Medium-High (Simple factors = Easy to front-run by HFT/algos)

---

## Current Implementation Analysis

### ✅ What's Working

1. **Multi-Factor Approach**

   - Uses momentum, volume, volatility
   - Z-score normalization (good for cross-sectional comparison)
   - Composite scoring with weights

2. **Technical Indicators**

   - RSI, EMAs, MACD (industry standard)
   - ATR for volatility
   - Multiple return windows (5, 10, 20 days)

3. **Data Quality Filters**
   - Minimum price ($5)
   - Minimum volume (500k)
   - Maximum volatility (100%)
   - Required factor validation

### ❌ Critical Weaknesses for Short-Term Trading

#### 1. **Factor Sophistication: TOO SIMPLE**

**Current:**

```python
momentum_raw = average(5d_return, 10d_return, 20d_return)
```

**Problems:**

- Equal weighting of different periods
- No decay function (recent data should matter more)
- No volatility adjustment
- No regime detection

**Modern Approach:**

- Exponentially weighted returns
- Sharpe-adjusted momentum
- Regime-conditional factors
- Intraday momentum (first hour, last hour)

#### 2. **Volume Analysis: BASIC**

**Current:**

```python
volume_ratio = current_volume / 20d_avg_volume
```

**Missing:**

- Volume price correlation
- Unusual volume spikes (>3σ)
- Volume-weighted average price (VWAP) distance
- Order flow toxicity indicators
- Relative volume vs sector/market

#### 3. **Volatility: NOT ACTIONABLE**

**Current:**

- Only used as filter and inverse scoring
- Single 20-day lookback

**Missing:**

- Volatility term structure (short vs long)
- Volatility regime changes
- Volatility skew
- Realized vs implied volatility gap
- Gamma exposure levels

#### 4. **NO RISK MANAGEMENT**

**Current:** None

**Critical Missing:**

- Position sizing rules
- Stop-loss levels
- Portfolio correlation
- Maximum drawdown limits
- Sector/factor concentration limits
- Kelly criterion or similar

#### 5. **NO MARKET REGIME AWARENESS**

**Current:** Same strategy all the time

**Missing:**

- VIX level consideration
- Market breadth (advance/decline)
- Sector rotation signals
- Fed policy stance
- Earnings season adjustments

#### 6. **NO TIMING SIGNALS**

**Current:** Only 9am and 10am scans

**Missing:**

- Entry trigger conditions
- Exit signals
- Time-of-day effects
- Day-of-week seasonality
- Earnings/event catalysts

#### 7. **LOOKBACK PERIODS: TOO SHORT**

**Current:** 30 days max

**Problem:**

- Can't detect longer-term trends
- No multi-timeframe analysis
- Missing structural breaks

---

## Groq AI Model Assessment

**Model:** llama-3.3-70b-versatile

### ✅ Strengths

- Good at text generation and formatting
- Can provide qualitative analysis
- Fast response times
- Understands financial terminology

### ❌ Limitations for Quant Analysis

- **Not trained on real-time market data**
- **Can't do numerical calculations** (no live data processing)
- **No statistical modeling capabilities**
- **Generic advice** (not backtested)
- **Hallucination risk** on specific prices/numbers

**Verdict:** Groq is fine for **report formatting and narrative**, but **ALL QUANTITATIVE SIGNALS** must come from your Python code, not the AI.

---

## Recommended Enhancements

### 🔴 CRITICAL (Implement First)

#### 1. **Enhanced Momentum Scoring**

```python
def calculate_momentum_score(df):
    """Multi-timeframe momentum with decay"""
    returns = {
        1: df['Close'].pct_change(1).iloc[-1],   # 1-day
        5: df['Close'].pct_change(5).iloc[-1],   # 1-week
        20: df['Close'].pct_change(20).iloc[-1], # 1-month
    }

    # Exponential decay weights (recent data matters more)
    weights = {1: 0.5, 5: 0.3, 20: 0.2}

    # Volatility-adjusted (Sharpe-like)
    vol = df['Close'].pct_change().std() * np.sqrt(252)

    momentum = sum(returns[w] * weights[w] for w in returns) / vol
    return momentum
```

#### 2. **Volume Anomaly Detection**

```python
def detect_volume_spike(df):
    """Identify unusual volume"""
    vol_20d = df['Volume'].iloc[-20:]
    current_vol = df['Volume'].iloc[-1]

    mean = vol_20d.mean()
    std = vol_20d.std()

    z_score = (current_vol - mean) / std

    return {
        'is_spike': z_score > 3,  # >3 sigma
        'z_score': z_score,
        'percentile': (vol_20d < current_vol).sum() / len(vol_20d)
    }
```

#### 3. **Risk Management Framework**

```python
class RiskManager:
    MAX_POSITION_SIZE = 0.1  # 10% of portfolio
    STOP_LOSS_PCT = 0.05     # 5% stop loss
    MAX_DAILY_LOSS = 0.02    # 2% max daily loss
    MAX_SECTOR_EXPOSURE = 0.3 # 30% per sector

    def calculate_position_size(self, signal_score, volatility, portfolio_value):
        """Kelly criterion-based sizing"""
        # Simplified Kelly: f = edge / odds
        edge = signal_score  # Your composite score
        odds = volatility    # Risk measure

        kelly_fraction = edge / odds if odds > 0 else 0
        kelly_fraction = min(kelly_fraction, self.MAX_POSITION_SIZE)

        position_value = portfolio_value * kelly_fraction
        return position_value

    def calculate_stop_loss(self, entry_price, atr):
        """ATR-based stop loss"""
        # 2x ATR below entry
        stop_price = entry_price - (2 * atr)
        return max(stop_price, entry_price * (1 - self.STOP_LOSS_PCT))
```

#### 4. **Market Regime Detection**

```python
def get_market_regime():
    """Determine current market conditions"""
    # Fetch VIX, SPY, market breadth
    vix = get_vix_level()  # Implement via API

    if vix < 15:
        return "LOW_VOL"  # Momentum strategies work
    elif vix < 25:
        return "NORMAL"   # Balanced approach
    else:
        return "HIGH_VOL" # Mean reversion, risk-off
```

### 🟡 IMPORTANT (Next Priority)

#### 5. **Intraday Timing Signals**

- First 30-min momentum
- Last hour reversal patterns
- VWAP distance
- Opening gap analysis

#### 6. **Multi-Timeframe Confluence**

- Daily trend + Hourly entry
- Weekly support/resistance
- Multiple timeframe RSI agreement

#### 7. **Sector Rotation Signals**

- Relative strength vs sector ETF
- Sector breadth indicators
- Inter-sector momentum

### 🟢 NICE-TO-HAVE (Future)

#### 8. **Machine Learning Enhancements**

- Random Forest for feature selection
- XGBoost for non-linear patterns
- LSTM for sequence prediction
- Reinforcement learning for timing

#### 9. **Alternative Data**

- Social media sentiment
- Options flow (put/call ratios)
- Insider trading activity
- Short interest changes

#### 10. **Portfolio Optimization**

- Mean-variance optimization
- Factor exposure balancing
- Transaction cost modeling
- Tax-loss harvesting

---

## Specific Code Improvements Needed

### File: `factors.py`

**ADD:**

```python
@staticmethod
def calculate_advanced_momentum(df: pd.DataFrame) -> Dict[str, float]:
    """Enhanced momentum with multiple dimensions"""
    factors = {}

    # 1. Exponentially weighted momentum
    returns_1d = df['Close'].pct_change(1).iloc[-1]
    returns_5d = df['Close'].pct_change(5).iloc[-1]
    returns_20d = df['Close'].pct_change(20).iloc[-1]

    ew_momentum = (0.5 * returns_1d + 0.3 * returns_5d + 0.2 * returns_20d)
    factors['momentum_ew'] = ew_momentum

    # 2. Sharpe-adjusted momentum
    returns = df['Close'].pct_change().dropna()
    if len(returns) >= 20:
        sharpe = returns.mean() / returns.std() * np.sqrt(252)
        factors['momentum_sharpe'] = sharpe

    # 3. Consistency score (% of positive days)
    if len(returns) >= 20:
        consistency = (returns.iloc[-20:] > 0).sum() / 20
        factors['momentum_consistency'] = consistency

    # 4. Acceleration (2nd derivative)
    if len(df) >= 40:
        mom_20d_current = (df['Close'].iloc[-1] / df['Close'].iloc[-21] - 1)
        mom_20d_prev = (df['Close'].iloc[-21] / df['Close'].iloc[-41] - 1)
        acceleration = mom_20d_current - mom_20d_prev
        factors['momentum_acceleration'] = acceleration

    return factors

@staticmethod
def calculate_volume_quality(df: pd.DataFrame) -> Dict[str, float]:
    """Advanced volume analysis"""
    factors = {}

    # Volume-price correlation (smart money indicator)
    if len(df) >= 20:
        price_change = df['Close'].pct_change().iloc[-20:]
        volume_change = df['Volume'].pct_change().iloc[-20:]
        corr = price_change.corr(volume_change)
        factors['volume_price_corr'] = corr

    # On-balance volume trend
    obv = (df['Volume'] * np.sign(df['Close'].diff())).cumsum()
    factors['obv_trend'] = obv.iloc[-1] / obv.iloc[-20] - 1 if len(obv) >= 20 else None

    # Volume spike detection
    vol_mean = df['Volume'].iloc[-20:].mean()
    vol_std = df['Volume'].iloc[-20:].std()
    current_vol = df['Volume'].iloc[-1]
    factors['volume_zscore'] = (current_vol - vol_mean) / vol_std if vol_std > 0 else 0

    return factors

@staticmethod
def calculate_volatility_regime(df: pd.DataFrame) -> Dict[str, float]:
    """Volatility analysis for regime detection"""
    factors = {}

    returns = df['Close'].pct_change().dropna()

    # Short-term vs long-term volatility
    vol_5d = returns.iloc[-5:].std() * np.sqrt(252) * 100
    vol_20d = returns.iloc[-20:].std() * np.sqrt(252) * 100

    factors['vol_5d'] = vol_5d
    factors['vol_regime'] = vol_5d / vol_20d if vol_20d > 0 else 1

    # Volatility trend
    if len(returns) >= 40:
        vol_recent = returns.iloc[-20:].std()
        vol_older = returns.iloc[-40:-20].std()
        factors['vol_trend'] = vol_recent / vol_older - 1

    return factors
```

### File: `scoring.py`

**MODIFY:**

```python
@staticmethod
def calculate_composite_score(factors: Dict[str, Any]) -> Dict[str, float]:
    """Enhanced scoring with regime awareness"""

    # Get market regime (you'd fetch VIX here)
    regime = "NORMAL"  # Placeholder

    if regime == "LOW_VOL":
        # Favor momentum in low vol
        weights = {
            'momentum_ew': 0.4,
            'momentum_sharpe': 0.2,
            'volume_zscore': 0.2,
            'volatility': 0.2
        }
    elif regime == "HIGH_VOL":
        # Favor quality and low volatility
        weights = {
            'momentum_sharpe': 0.3,
            'volume_price_corr': 0.3,
            'volatility': 0.4  # Higher weight on stability
        }
    else:
        # Balanced
        weights = scan_config.FACTOR_WEIGHTS

    # Calculate weighted score
    score = sum(factors.get(f'z_{k}', 0) * v for k, v in weights.items())

    return {
        'composite_score': round(score, 4),
        'regime': regime
    }
```

### NEW FILE: `risk_management.py`

```python
"""Risk management and position sizing"""

import numpy as np
from typing import Dict, List
from .config import scan_config

class RiskManager:
    """Position sizing and risk controls"""

    # Portfolio-level limits
    MAX_PORTFOLIO_RISK = 0.02  # 2% max daily portfolio loss
    MAX_POSITION_SIZE = 0.10   # 10% per position
    MAX_SECTOR_EXPOSURE = 0.30  # 30% per sector

    # Trade-level limits
    STOP_LOSS_ATR_MULTIPLE = 2.0
    MIN_RISK_REWARD = 2.0  # Minimum 2:1 reward:risk

    @staticmethod
    def calculate_position_size(
        signal_score: float,
        volatility: float,
        portfolio_value: float,
        current_positions: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate optimal position size using Kelly criterion

        Returns:
            {
                'shares': int,
                'position_value': float,
                'risk_amount': float,
                'stop_loss': float
            }
        """
        # Simplified Kelly: f = edge / odds
        # Edge = signal score (assume 0-1 range)
        # Odds = volatility (risk)

        kelly_fraction = signal_score / volatility if volatility > 0 else 0
        kelly_fraction = min(kelly_fraction, RiskManager.MAX_POSITION_SIZE)

        # Half-Kelly for safety
        kelly_fraction *= 0.5

        position_value = portfolio_value * kelly_fraction

        return {
            'position_fraction': kelly_fraction,
            'position_value': position_value,
            'max_risk': position_value * RiskManager.MAX_PORTFOLIO_RISK
        }

    @staticmethod
    def calculate_stops(
        entry_price: float,
        atr: float,
        signal_score: float
    ) -> Dict[str, float]:
        """
        Calculate stop loss and take profit levels
        """
        # ATR-based stop loss
        stop_loss = entry_price - (RiskManager.STOP_LOSS_ATR_MULTIPLE * atr)

        # Risk-reward based take profit
        risk = entry_price - stop_loss
        take_profit = entry_price + (risk * RiskManager.MIN_RISK_REWARD)

        return {
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'risk_dollars': round(risk, 2),
            'reward_dollars': round(take_profit - entry_price, 2)
        }
```

---

## Backtesting Framework (CRITICAL MISSING)

**You MUST backtest before live trading!**

### Add: `backtest.py`

```python
"""Simple backtesting framework"""

import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime, timedelta

class Backtester:
    """Backtest trading strategies"""

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

    def run_backtest(
        self,
        signals_history: List[Dict],  # Historical signals
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Run backtest on historical signals

        Returns performance metrics
        """
        # Sort signals by date
        signals = sorted(signals_history, key=lambda x: x['date'])

        for signal in signals:
            # Simulate trade execution
            self._execute_signal(signal)

            # Update equity curve
            self.equity_curve.append({
                'date': signal['date'],
                'equity': self._calculate_equity()
            })

        return self._calculate_performance()

    def _calculate_performance(self) -> Dict:
        """Calculate backtest metrics"""
        equity_df = pd.DataFrame(self.equity_curve)

        returns = equity_df['equity'].pct_change().dropna()

        total_return = (self.capital / self.initial_capital - 1) * 100
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        max_dd = self._calculate_max_drawdown(equity_df['equity'])

        win_rate = len([t for t in self.trades if t['pnl'] > 0]) / len(self.trades) if self.trades else 0

        return {
            'total_return_pct': round(total_return, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown_pct': round(max_dd * 100, 2),
            'total_trades': len(self.trades),
            'win_rate': round(win_rate * 100, 2),
            'final_capital': round(self.capital, 2)
        }

    @staticmethod
    def _calculate_max_drawdown(equity_series: pd.Series) -> float:
        """Calculate maximum drawdown"""
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        return drawdown.min()
```

---

## Implementation Priority

### Phase 1: Foundation (Week 1-2)

1. ✅ Add enhanced momentum factors
2. ✅ Add volume quality metrics
3. ✅ Add volatility regime detection
4. ✅ Implement risk management module

### Phase 2: Risk & Validation (Week 3-4)

5. ✅ Build backtesting framework
6. ✅ Backtest current strategy (2023-2024 data)
7. ✅ Implement position sizing
8. ✅ Add stop loss/take profit logic

### Phase 3: Enhancement (Month 2)

9. ⚠️ Add market regime awareness
10. ⚠️ Implement intraday timing signals
11. ⚠️ Add sector rotation logic
12. ⚠️ Multi-timeframe confluence

### Phase 4: Advanced (Month 3+)

13. 🔮 Machine learning models
14. 🔮 Alternative data integration
15. 🔮 Portfolio optimization
16. 🔮 Live execution system

---

## Critical Warning

**DO NOT TRADE LIVE WITH CURRENT SYSTEM**

Reasons:

1. ❌ No backtested performance data
2. ❌ No risk management
3. ❌ No position sizing rules
4. ❌ Too simple factors (easy to front-run)
5. ❌ No stop losses
6. ❌ No market regime awareness

**Minimum Requirements for Live Trading:**

- ✅ 2+ years backtest with Sharpe > 1.5
- ✅ Maximum drawdown < 20%
- ✅ Win rate > 50%
- ✅ Risk management implemented
- ✅ Paper trading for 3+ months

---

## Next Steps

1. **Immediate (Today):**

   - Review this analysis
   - Decide on enhancement priorities
   - Set up backtesting data source

2. **This Week:**

   - Implement Phase 1 enhancements
   - Build basic backtest framework
   - Test on 2024 data

3. **Next 2 Weeks:**

   - Add risk management
   - Backtest multiple scenarios
   - Refine factor weights

4. **Month 2:**
   - Add advanced features
   - Paper trade with real signals
   - Monitor performance vs backtest

---

## Conclusion

**Current System:** 5/10 for screening, 2/10 for trading

**With Enhancements:** Could reach 7-8/10

**Groq AI:** Good for reports, not for signals

**Action Required:** MAJOR enhancements before any live capital

**Time to Production-Ready:** 2-3 months minimum

---

**Questions to Consider:**

1. What's your risk tolerance? (Max acceptable loss per trade/day)
2. What's your target return? (Need to know to size bets)
3. How much capital are you trading? (Affects strategy choice)
4. Can you dedicate time to monitor trades? (Affects automation needs)
5. Do you want fully automated or human-in-loop?

Let me know your answers and I'll prioritize the enhancements accordingly.
