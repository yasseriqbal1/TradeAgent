"""Dip suggestions engine for the dashboard.

Goal: provide simple, explainable “dip” opportunities using *existing* live rates
already available in the system (Redis `live_prices` via the dashboard).

This is intentionally lightweight:
- No external dependencies
- Minimal state persisted in Redis (or in-memory fallback)
- Heuristic scoring (not a predictive model)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Any, Dict, List, Optional, Tuple


STATE_KEY = "dip_suggest_state_v1"


@dataclass(frozen=True)
class DipSuggestion:
    ticker: str
    price: float
    score: float
    priority: str
    drawdown_from_high_pct: float
    last_tick_change_pct: float
    reasons: List[str]


_IN_MEMORY_STATE: Dict[str, Any] = {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _load_state(redis_client: Any, today_key: str) -> Dict[str, Any]:
    if redis_client is not None:
        try:
            raw = redis_client.get(STATE_KEY)
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("date") == today_key:
                    return parsed
        except Exception:
            pass

    # In-memory fallback (non-persistent)
    state = _IN_MEMORY_STATE.get(STATE_KEY)
    if isinstance(state, dict) and state.get("date") == today_key:
        return state
    return {"date": today_key, "tickers": {}}


def _save_state(redis_client: Any, state: Dict[str, Any]) -> None:
    if redis_client is not None:
        try:
            # Keep for a couple days to avoid stale build-up.
            redis_client.setex(STATE_KEY, 172800, json.dumps(state))
            return
        except Exception:
            pass
    _IN_MEMORY_STATE[STATE_KEY] = state


def _priority_from_score(score: float, drawdown_pct: float, reversal: bool) -> Optional[str]:
    # Conservative gating: only “URGENT” when both a meaningful dip AND a reversal signal exist.
    if reversal and drawdown_pct <= -8.0 and score >= 80:
        return "URGENT"
    if drawdown_pct <= -6.0 and score >= 65:
        return "HIGH"
    if drawdown_pct <= -4.0 and score >= 45:
        return "MEDIUM"
    if drawdown_pct <= -3.0 and score >= 30:
        return "LOW"
    return None


def compute_dip_suggestions(
    live_prices: List[Dict[str, Any]],
    *,
    redis_client: Any = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Compute dip suggestions from live price snapshots.

    `live_prices` is expected to be a list of dicts like:
      {"ticker": "AAPL", "price": 190.12, "change_pct": -0.35}

    The engine maintains a minimal per-ticker state:
    - session high (since dashboard process started / daily reset)
    - EMA fast/slow (intraday)
    - last price and last tick return
    """

    now = now or datetime.now()
    today_key = now.strftime("%Y-%m-%d")

    max_items = int(os.getenv("DIP_SUGGEST_MAX_ITEMS", "8") or "8")
    min_drawdown = _safe_float(os.getenv("DIP_SUGGEST_MIN_DRAWDOWN_PCT", "3.0"), 3.0)
    exclude_raw = (os.getenv("DIP_SUGGEST_EXCLUDE_TICKERS", "") or "").strip()
    exclude = {t.strip().upper() for t in exclude_raw.split(",") if t.strip()}

    state = _load_state(redis_client, today_key)
    tickers_state: Dict[str, Any] = state.get("tickers") if isinstance(state.get("tickers"), dict) else {}
    state["tickers"] = tickers_state

    suggestions: List[DipSuggestion] = []

    alpha_fast = 0.25
    alpha_slow = 0.08

    for item in live_prices:
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker or ticker in exclude:
            continue

        price = _safe_float(item.get("price"), 0.0)
        if price <= 0:
            continue

        prev = tickers_state.get(ticker) or {}
        prev_price = _safe_float(prev.get("last_price"), 0.0)
        prev_ret = _safe_float(prev.get("last_ret"), 0.0)
        prev_down_streak = int(prev.get("down_streak") or 0)
        prev_ema_fast = _safe_float(prev.get("ema_fast"), price)
        prev_ema_slow = _safe_float(prev.get("ema_slow"), price)

        # Session high/low
        high = max(_safe_float(prev.get("high"), price), price)
        low = min(_safe_float(prev.get("low"), price), price)

        # Tick return
        last_ret = 0.0
        if prev_price > 0:
            last_ret = ((price - prev_price) / prev_price) * 100.0

        # Down-streak tracking (helps detect “selloff then bounce”)
        down_streak = prev_down_streak
        if last_ret < -0.05:
            down_streak = min(down_streak + 1, 50)
        elif last_ret > 0.05:
            down_streak = 0

        # EMAs (intraday proxies)
        ema_fast = (alpha_fast * price) + ((1 - alpha_fast) * prev_ema_fast)
        ema_slow = (alpha_slow * price) + ((1 - alpha_slow) * prev_ema_slow)

        drawdown_pct = ((price - high) / high) * 100.0 if high > 0 else 0.0

        # Reversal heuristic: positive tick after at least one negative tick, plus a reclaim of fast EMA.
        reversal = (last_ret > 0.15 and prev_ret < 0) or (price > ema_fast and prev_price < prev_ema_fast)
        trend_ok = ema_fast >= ema_slow

        # Simple convex scoring: emphasize dip size; add small bonuses for reversal/trend.
        dd_score = max(0.0, min(70.0, (-drawdown_pct) * 6.0))
        reversal_bonus = 20.0 if reversal else 0.0
        trend_bonus = 10.0 if trend_ok else 0.0
        score = round(dd_score + reversal_bonus + trend_bonus, 1)

        # Persist state update
        tickers_state[ticker] = {
            "high": high,
            "low": low,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "last_price": price,
            "last_ret": last_ret,
            "down_streak": down_streak,
            "updated_at": now.isoformat(timespec="seconds"),
        }

        # Gate: only show meaningful dips
        if drawdown_pct > -abs(min_drawdown):
            continue

        priority = _priority_from_score(score, drawdown_pct, reversal)
        if not priority:
            continue

        reasons: List[str] = [f"Down {abs(drawdown_pct):.1f}% from session high"]
        if reversal:
            reasons.append(f"Reversal tick: {last_ret:+.2f}%")
        if trend_ok:
            reasons.append("Intraday trend: fast EMA ≥ slow EMA")

        suggestions.append(
            DipSuggestion(
                ticker=ticker,
                price=round(price, 4),
                score=score,
                priority=priority,
                drawdown_from_high_pct=round(drawdown_pct, 2),
                last_tick_change_pct=round(last_ret, 2),
                reasons=reasons,
            )
        )

    _save_state(redis_client, state)

    # Sort by urgency then score
    priority_rank = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    suggestions.sort(key=lambda s: (priority_rank.get(s.priority, 9), -s.score, s.ticker))

    items = [
        {
            "ticker": s.ticker,
            "price": s.price,
            "score": s.score,
            "priority": s.priority,
            "drawdown_from_high_pct": s.drawdown_from_high_pct,
            "last_tick_change_pct": s.last_tick_change_pct,
            "reasons": s.reasons,
        }
        for s in suggestions[: max_items]
    ]

    return {
        "generated_at": now.strftime("%I:%M:%S %p"),
        "items": items,
        "notes": "Heuristic signals from live prices only; informational, not financial advice.",
    }
