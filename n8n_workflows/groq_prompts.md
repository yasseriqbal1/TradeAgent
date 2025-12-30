# Groq AI Prompts for TradeAgent

## Overview

TradeAgent uses Groq's Llama 3.1 70B model for generating human-readable summaries and analysis of technical trading signals.

## Model Configuration

- **Model**: `llama-3.1-70b-versatile`
- **Temperature**: 0.5-0.7 (balanced creativity/consistency)
- **Max Tokens**: 800-1500
- **API**: https://api.groq.com/openai/v1/chat/completions

---

## Prompt 1: Pre-Market Scan Analysis (9:00 AM EST)

### System Message

```
You are a quantitative trading analyst. Analyze stock signals objectively.
Highlight risks and opportunities. Never guarantee returns.
Focus on technical factors and risk management. Keep analysis concise and actionable.
```

### User Message Template

```
Date: {current_date}

Top 10 stocks from multi-factor technical scan:

{json_signals}

Provide:
1. Market Summary (2-3 sentences on overall signals)
2. Top 3 Picks Analysis (for each stock):
   - Ticker and key strengths
   - Technical factors driving selection (momentum, RSI, volume, volatility)
   - Risk factors (high volatility, sector concentration, liquidity concerns)
3. Watchlist (remaining 7 stocks, 1 line each with key metric)
4. Risk Disclaimer

Format in clear sections. Be specific about numbers. Emphasize this is a research tool, not advice.
```

### Expected Output Format

```
MARKET SUMMARY
[2-3 sentences about overall market technical signals, sector themes, risk levels]

TOP 3 PICKS

1. TICKER - Score: X.XXX
Strengths: [momentum/volume/technical factors]
Risks: [volatility/liquidity/sector concerns]

2. TICKER - Score: X.XXX
[...]

3. TICKER - Score: X.XXX
[...]

WATCHLIST
4. TICKER - [1 line key metric]
5. TICKER - [1 line key metric]
[...]

RISK DISCLAIMER
[Standard disclaimer about research vs advice, 5-20 day horizon, need for risk management]
```

---

## Prompt 2: Validation Scan Analysis (10:00 AM EST)

### System Message

```
You are a quantitative trading analyst. Provide concise alerts about market changes.
Focus on material changes only. Be direct and actionable.
```

### User Message Template

```
10:00 AM Validation Scan - Changes Detected

Dropped Tickers: {dropped_list}
Added Tickers: {added_list}
Significant Score Changes: {score_changes_list}
Significant Price Moves: {price_moves_list}

Provide:
1. Quick Summary (2-3 sentences on what changed and why it matters)
2. Action Items (specific things to watch or adjust)
3. Risk Alert (if any major concerns like gap downs, volatility spikes)

Be direct and actionable. No fluff.
```

### Expected Output Format

```
QUICK SUMMARY
[2-3 sentences on material changes and their significance]

ACTION ITEMS
• [Specific action 1]
• [Specific action 2]
• [Specific action 3]

RISK ALERT
[Only if material: gap downs >5%, volatility spikes >2x, liquidity drying up]
```

---

## Prompt Guidelines

### DO:

- **Be specific with numbers**: "RSI at 72 indicates overbought" not "RSI is high"
- **Quantify risk**: "20-day volatility at 45%" not "volatile"
- **Focus on technical factors**: Momentum, volume, volatility, RSI, EMAs
- **Emphasize 5-20 day horizon**: These are swing trade setups
- **Include disclaimers**: Not advice, research only, risk management required
- **Be concise**: 800-1500 tokens total

### DON'T:

- **Never guarantee returns**: No "will go up", "guaranteed profit"
- **No fundamentals**: Earnings, P/E, etc. (not in our data yet)
- **No predictions**: "likely to rally" → "showing momentum strength"
- **No fluff**: Get to the point quickly
- **No jargon overload**: Balance technical terms with clarity

---

## Example Input/Output

### Example Pre-Market Input

```json
{
  "signals": [
    {
      "rank": 1,
      "ticker": "NVDA",
      "score": "1.847",
      "price": "493.25",
      "momentum": {
        "return_10d": "8.50",
        "rsi": "68.3",
        "z_score": "1.85"
      },
      "volatility": {
        "vol_20d": "32.5",
        "atr_pct": "2.10",
        "z_score": "-0.45"
      },
      "volume": {
        "ratio": "1.85",
        "z_score": "1.20"
      }
    }
  ]
}
```

### Example Pre-Market Output

```
MARKET SUMMARY
Strong momentum signals across tech and industrial sectors. 8 of 10 picks showing positive 10-day returns averaging +6.2%. Volatility mostly contained (avg 28%), suggesting stable trend strength. Volume confirms institutional interest.

TOP 3 PICKS

1. NVDA - Score: 1.847
Strengths: Exceptional 10-day momentum (+8.5%), RSI 68.3 near overbought but not extreme, volume 1.85x average showing strong interest. Volatility 32.5% manageable for the sector.
Risks: Near overbought territory (RSI 68), high beta to market moves, semiconductor sector concentration.

[...]

RISK DISCLAIMER
This analysis is for educational/research purposes only and does not constitute financial advice. Technical signals have a 5-20 day horizon and require active risk management including stop-losses. Past performance does not guarantee future results. Consult a licensed financial advisor before making investment decisions.
```

---

## API Integration Code (Reference)

### Groq API Call Structure

```javascript
{
  "model": "llama-3.1-70b-versatile",
  "messages": [
    {
      "role": "system",
      "content": "[System message here]"
    },
    {
      "role": "user",
      "content": "[User message with data here]"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1500
}
```

### Response Structure

```javascript
{
  "choices": [
    {
      "message": {
        "content": "[AI generated analysis here]"
      }
    }
  ],
  "usage": {
    "total_tokens": 1234
  }
}
```

---

## Groq API Key Setup

**In n8n:**

1. Settings → Environments
2. Add variable: `GROQ_API_KEY`
3. Value: `xxxxx`

**In HTTP Request nodes:**

- Header: `Authorization: Bearer {{ $env.GROQ_API_KEY }}`
- Header: `Content-Type: application/json`

---

## Error Handling

**If Groq API fails:**

- Timeout: 30 seconds
- Fallback: Send email with raw data (no AI summary)
- Log error in n8n execution history

**Rate Limits:**

- Groq free tier: Check console.groq.com for limits
- If exceeded: Consider upgrading or adding delay between calls

---

## Tuning Tips

**To make AI more conservative:**

- Lower temperature (0.5)
- Add "emphasize risks" to system message
- Increase max_tokens for more detailed risk discussion

**To make AI more technical:**

- Add "use quantitative metrics" to system message
- Request specific indicator values in output
- Lower temperature (0.4-0.5)

**To make AI more concise:**

- Lower max_tokens (800)
- Add "be extremely concise" to system message
- Request bullet point format
