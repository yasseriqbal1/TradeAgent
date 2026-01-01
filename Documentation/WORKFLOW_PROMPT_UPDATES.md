# Workflow Prompt Updates for Phase 1 Risk Management

## Overview

The Python backend now includes enhanced factors and risk management. Update the Groq AI prompts in both n8n workflows to utilize the new risk metrics.

## Changes Made to Backend

### 1. Enhanced Factors (factors.py)

- **Exponential Momentum**: Recent price moves weighted more heavily (1d=50%, 5d=30%, 20d=20%)
- **Sharpe Momentum**: Risk-adjusted returns (return per unit of volatility)
- **Momentum Consistency**: Percentage of positive days in last 20 days
- **Momentum Acceleration**: Comparing recent vs older momentum
- **Volume-Price Correlation**: Quality of price moves with volume confirmation
- **Volume Z-Score**: Spike detection (unusual volume activity)
- **OBV Trend**: On-Balance Volume trend analysis
- **Volatility Regime**: Short-term vs long-term volatility ratio
- **Volatility Trend**: Whether volatility is expanding or contracting

### 2. Risk Management Module (risk_management.py)

Each signal now includes a `trade_plan` object with:

- **Position Sizing**: Kelly criterion-based, adjusted by composite score
  - `shares`: Number of shares to buy
  - `position_value`: Dollar value of position
  - `position_pct`: Percentage of portfolio
- **Stop Loss**: ATR-based stop loss (2x ATR below entry)
  - `stop_loss`: Stop loss price
  - `stop_loss_pct`: Stop loss percentage from entry
- **Take Profit**: 2:1 risk-reward target
  - `take_profit`: Target price
  - `take_profit_pct`: Target percentage from entry
- **Risk Metrics**:
  - `risk_per_share`: Dollar risk per share
  - `total_risk`: Total dollar amount at risk
  - `portfolio_risk_pct`: Percentage of portfolio at risk
  - `quality_score`: 0-100 quality rating based on factors
  - `reward_risk_ratio`: 2.0 (2:1 minimum)
- **Validation**:
  - `valid`: Whether trade passes risk checks
  - `warnings`: Any risk management warnings

## Updated Workflows

### Premarket Scan Workflow (9:00 AM)

**Node: "Format Data for AI"**
Update the JavaScript code to include risk metrics:

```javascript
// Format scan results for Groq AI with RISK METRICS
const scanData = $input.item.json;

if (scanData.status !== "success") {
  throw new Error("Scan failed: " + (scanData.error || "Unknown error"));
}

// Extract signals with trade plans
const signals = scanData.signals || [];

// Build comprehensive summary with risk metrics
const signalSummary = signals.map((s, idx) => {
  const factors = s.factors || {};
  const tradePlan = factors.trade_plan || {}; // NEW: Get trade plan

  return {
    rank: idx + 1,
    ticker: s.ticker,
    score: s.composite_score?.toFixed(3),
    price: s.price?.toFixed(2),

    // Enhanced momentum metrics
    momentum: {
      return_10d: factors.momentum?.return_10d?.toFixed(2),
      momentum_exp: factors.momentum?.momentum_exp?.toFixed(2),
      sharpe: factors.momentum?.sharpe_momentum?.toFixed(2),
      consistency: factors.momentum?.momentum_consistency?.toFixed(1),
      rsi: factors.momentum?.rsi_14?.toFixed(1),
      z_score: factors.momentum?.z_score?.toFixed(2),
    },

    // Enhanced volatility metrics
    volatility: {
      vol_20d: factors.volatility?.volatility_20d?.toFixed(1),
      atr_pct: factors.volatility?.atr_pct?.toFixed(2),
      regime: factors.volatility?.vol_regime?.toFixed(2),
      z_score: factors.volatility?.z_score?.toFixed(2),
    },

    // Enhanced volume metrics
    volume: {
      ratio: factors.volume?.volume_ratio?.toFixed(2),
      price_corr: factors.volume?.volume_price_corr?.toFixed(2),
      zscore: factors.volume?.volume_zscore?.toFixed(2),
      dollar_vol: factors.volume?.dollar_volume,
      z_score: factors.volume?.z_score?.toFixed(2),
    },

    // NEW: Risk management metrics
    trade_plan: {
      entry: tradePlan.entry_price,
      shares: tradePlan.shares,
      position_value: tradePlan.position_value,
      position_pct: tradePlan.position_pct?.toFixed(2),
      stop_loss: tradePlan.stop_loss,
      stop_pct: tradePlan.stop_loss_pct?.toFixed(2),
      target: tradePlan.take_profit,
      target_pct: tradePlan.take_profit_pct?.toFixed(2),
      risk: tradePlan.total_risk,
      risk_pct: tradePlan.portfolio_risk_pct?.toFixed(2),
      quality: tradePlan.quality_score,
      valid: tradePlan.valid,
      warnings: tradePlan.warnings,
    },
  };
});

return {
  scan_timestamp: scanData.timestamp,
  execution_time: scanData.execution_time,
  stats: scanData.stats,
  signals: signalSummary,
};
```

**Node: "Groq AI - Generate Summary"**
Update the `messages` parameter body content (the user prompt):

```javascript
`Date: ${new Date().toLocaleDateString("en-US", {
  timeZone: "America/New_York",
})}

PORTFOLIO CONTEXT:
- Portfolio Size: $100,000
- Max Position Size: 10% ($10,000)
- Max Risk Per Trade: 2% ($2,000)
- Risk-Reward Ratio: 2:1 minimum

TOP SIGNALS WITH RISK MANAGEMENT:

${JSON.stringify($json.signals, null, 2)}

ANALYSIS REQUIRED:
1. Market Summary (2-3 sentences on overall technical environment)

2. Top 3 Trade Recommendations (for each):
   - Ticker and Entry Price
   - Position Size (shares + dollar amount + % of portfolio)
   - Technical Rationale (use exponential momentum, Sharpe ratio, volume quality metrics)
   - Entry Strategy: Specific stop loss price and take profit target
   - Risk Assessment: Dollar risk, quality score (0-100), warnings if any
   - Time Horizon: 1-5 days typical

3. Remaining Watchlist (tickers 4-10):
   - One line per ticker with score, entry, and key strength

4. Portfolio Risk Summary:
   - Total capital deployed if all trades taken
   - Total portfolio risk exposure
   - Any risk warnings across positions

5. Risk Disclaimer (standard trading risk language)

FORMAT: Clear sections with specific numbers. Use bullet points. Be concise but complete on risk metrics.`;
```

### Validation Scan Workflow (10:00 AM)

**Node: "Format Data for AI"**
Same changes as premarket - add trade_plan extraction.

**Node: "Groq AI - Generate Summary"**
Update the `messages` parameter body content:

```javascript
`Date: ${new Date().toLocaleDateString("en-US", {
  timeZone: "America/New_York",
})}
Time: 10:00 AM EST (1 Hour After Market Open)

VALIDATION SCAN - Comparing 9am premarket vs current market conditions

CURRENT SIGNALS WITH UPDATED RISK METRICS:
${JSON.stringify($json.signals, null, 2)}

CHANGES FROM PREMARKET:
${JSON.stringify($json.changes, null, 2)}

PORTFOLIO CONTEXT:
- Portfolio Size: $100,000
- Max Position Size: 10% per stock
- Max Risk Per Trade: 2%

ANALYSIS REQUIRED:

1. Change Summary:
   - Tickers dropped from premarket (and why)
   - New tickers added (and catalysts)
   - Significant price moves (>2%)
   - Score changes (momentum shifts)

2. Position Adjustments:
   - Which premarket picks remain valid (confirm entry/stops)
   - Which should be avoided (deteriorating technicals)
   - Any stop loss updates needed
   - New opportunities from validation

3. Active Trade Management:
   - If holding positions from yesterday, any exit signals?
   - Stop loss adjustments based on new volatility
   - Profit-taking levels if momentum weakening

4. Updated Top 5 Recommendations:
   - Ticker, entry, shares, stop, target
   - Updated quality scores
   - Risk per position

5. Risk Check:
   - Any correlation concerns (multiple tech stocks?)
   - Total portfolio risk if all trades active
   - Warnings or red flags

FORMAT: Action-oriented. Focus on CHANGES and what to DO differently from 9am analysis.`;
```

## How to Update Workflows in n8n

1. **Open n8n UI** (usually http://localhost:5678)

2. **For Premarket Workflow:**

   - Open workflow "TradeAgent - Premarket Scan"
   - Click on "Format Data for AI" node
   - Replace the JavaScript code with updated version above
   - Click on "Groq AI - Generate Summary" node
   - In the body parameters, update the "messages" value with new prompt
   - Save workflow

3. **For Validation Workflow:**

   - Open workflow "TradeAgent - Validation Scan"
   - Update "Format Data for AI" node
   - Update "Groq AI - Generate Summary" node with validation-specific prompt
   - Save workflow

4. **Test Workflows:**
   - Make sure FastAPI is running (port 8000)
   - Manually trigger each workflow
   - Verify output files contain risk metrics and trade plans
   - Check Desktop for output files: `TradeAgent_PreMarket_YYYY-MM-DD.txt` and `TradeAgent_Validation_YYYY-MM-DD.txt`

## Expected Output Format

Reports will now include:

### Individual Stock Analysis

```
TICKER: NVDA
Entry: $145.50
Position: 68 shares ($9,894 = 9.89% of portfolio)
Stop Loss: $141.20 (-2.96%)
Target: $152.10 (+4.54%)
Risk: $292.40 (0.29% of portfolio)
Quality Score: 78/100

Technical Factors:
- Exponential Momentum: +3.2% (strong recent strength)
- Sharpe Momentum: 0.45 (risk-adjusted positive)
- Momentum Consistency: 65% (13 of 20 days positive)
- Volume Quality: 0.72 correlation (institutional support)
- Volatility Regime: 0.85 (contracting volatility = potential breakout)

Trade Rationale: Strong technical momentum with institutional volume support...
```

### Portfolio Summary

```
Total Capital Deployed: $45,000 (45% of portfolio)
Total Portfolio Risk: $1,800 (1.8% of portfolio)
Number of Positions: 5
Average Quality Score: 72/100
Risk Warnings: None - all positions within limits
```

## Benefits of Phase 1 Enhancements

1. **Specific Entry/Exit Levels**: No more guessing - exact prices for stops and targets
2. **Position Sizing**: Automated calculation based on risk tolerance and signal quality
3. **Risk Quantification**: Know exactly how much you're risking per trade and portfolio-wide
4. **Quality Scoring**: 0-100 rating helps prioritize highest-conviction trades
5. **Enhanced Factors**: More sophisticated momentum, volume, and volatility analysis
6. **Validation Updates**: 10am scan can recommend stop/target adjustments based on market open

## Important Notes

- Trade plans assume $100,000 portfolio (configurable in risk_management.py)
- All position sizes respect 10% max position, 2% max risk per trade
- Stop losses are ATR-based (2x ATR = volatility-adjusted)
- Target prices use 2:1 risk-reward minimum
- Quality scores weight momentum consistency, volume quality, and volatility regime
- Validation scan focuses on CHANGES - what's different from 9am

## Next Steps (Post Phase 1)

Phase 1 provides actionable trade plans but does NOT include:

- Backtesting validation (requires Phase 2)
- Correlation analysis across portfolio
- Sector exposure limits
- Advanced timing signals
- Machine learning enhancements

**Do not use with live capital** until Phase 2 backtesting validates 2+ years of historical performance.
