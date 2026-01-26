"""Critical monitoring helpers for the dashboard.

This module is intentionally small and pragmatic:
- Fetch a couple of macro indicators (VIX, WTI) for context.
- Show any external critical alerts pushed into Redis (e.g., from n8n).

It does NOT attempt to scrape social media or news feeds directly.
For text/news monitoring, the recommended path is to push alerts in via automation
you control (n8n/webhooks) into Redis, and the dashboard will display them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import concurrent.futures
import json
import os
from typing import Any, Dict, List, Optional, Tuple


ALERTS_KEY = "critical_alerts_v1"
INDICATOR_CACHE_KEY = "critical_monitor_indicators_cache_v1"

_MEM_CACHE: Dict[str, Any] = {}


def _safe_float(value: Any) -> Optional[float]:
    try:
        f = float(value)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


def fetch_quote_yfinance(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    """Return (last_price, error). Uses yfinance if available."""
    try:
        import yfinance as yf  # type: ignore

        t = yf.Ticker(symbol)

        last_error: Optional[str] = None

        # fast_info tends to be lighter-weight than full history, but can throw for
        # some symbols depending on Yahoo's payload shape.
        fast_info: Dict[str, Any] = {}
        try:
            fi = getattr(t, "fast_info", None)
            if fi:
                fast_info = dict(fi)
        except Exception:
            fast_info = {}

        for key in ("lastPrice", "last_price", "regularMarketPrice", "last"):
            f = _safe_float(fast_info.get(key))
            if f is not None:
                return f, None

        # History fallback
        try:
            hist = t.history(period="5d", interval="1d")
            if hist is not None and len(hist) > 0 and "Close" in hist:
                v = hist["Close"].iloc[-1]
                f2 = _safe_float(v)
                if f2 is not None:
                    return f2, None
        except Exception as e:
            last_error = str(e)

        # Final fallback: download path sometimes succeeds when Ticker methods don't.
        try:
            hist2 = yf.download(symbol, period="5d", interval="1d", progress=False, threads=False)
            if hist2 is not None and len(hist2) > 0 and "Close" in hist2:
                v = hist2["Close"].iloc[-1]
                f3 = _safe_float(v)
                if f3 is not None:
                    return f3, None
        except Exception as e:
            last_error = str(e)

        if last_error:
            lower = last_error.lower()
            if "too many requests" in lower or "429" in lower:
                return None, "rate_limited"
            if "jsondecodeerror" in lower:
                return None, "bad_response"
        return None, "no_data"
    except Exception as e:
        return None, str(e)


def _get_cached_indicator_values(
    *, redis_client: Any, now: datetime, max_age_seconds: int
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Return cached values keyed by symbol, or None if missing/stale."""
    if max_age_seconds <= 0:
        return None

    # Prefer Redis cache when available.
    if redis_client:
        try:
            raw = redis_client.get(INDICATOR_CACHE_KEY)
            if raw:
                parsed = json.loads(raw)
                ts = parsed.get("ts")
                values = parsed.get("values")
                if ts and isinstance(values, dict):
                    cached_at = datetime.fromisoformat(ts)
                    age = (now - cached_at).total_seconds()
                    if age <= max_age_seconds:
                        return values
        except Exception:
            pass

    # Fallback to in-process cache.
    try:
        ts = _MEM_CACHE.get("ts")
        values = _MEM_CACHE.get("values")
        if isinstance(ts, datetime) and isinstance(values, dict):
            age = (now - ts).total_seconds()
            if age <= max_age_seconds:
                return values
    except Exception:
        pass

    return None


def _set_cached_indicator_values(*, redis_client: Any, now: datetime, values: Dict[str, Dict[str, Any]], ttl_seconds: int) -> None:
    payload = {"ts": now.isoformat(), "values": values}

    _MEM_CACHE["ts"] = now
    _MEM_CACHE["values"] = values

    if not redis_client:
        return
    try:
        ttl = max(int(ttl_seconds), 30)
        redis_client.setex(INDICATOR_CACHE_KEY, ttl, json.dumps(payload))
    except Exception:
        return


def classify_threshold(value: Optional[float], warn: float, critical: float) -> str:
    if value is None:
        return "unknown"
    if value >= critical:
        return "critical"
    if value >= warn:
        return "warning"
    return "ok"


def read_external_alerts(redis_client: Any, *, max_items: int = 8) -> List[Dict[str, Any]]:
    if not redis_client:
        return []
    try:
        raw = redis_client.get(ALERTS_KEY)
        if not raw:
            return []
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
        # newest first
        parsed = list(reversed(parsed))
        items = []
        for a in parsed[:max_items]:
            if not isinstance(a, dict):
                continue
            items.append(
                {
                    "ts": a.get("ts"),
                    "severity": (a.get("severity") or "info").lower(),
                    "title": a.get("title") or "Alert",
                    "message": a.get("message") or "",
                    "source": a.get("source") or "external",
                    "url": a.get("url"),
                    "matched": a.get("matched") if isinstance(a.get("matched"), list) else None,
                }
            )
        return items
    except Exception:
        return []


def build_critical_monitor_payload(*, redis_client: Any = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now()

    # Thresholds are configurable. Defaults reflect your examples.
    vix_warn = float(os.getenv("VIX_WARN", "20"))
    vix_critical = float(os.getenv("VIX_CRITICAL", "30"))
    wti_warn = float(os.getenv("WTI_WARN", "65"))
    wti_critical = float(os.getenv("WTI_CRITICAL", "80"))

    cache_seconds = int(os.getenv("CRITICAL_INDICATOR_CACHE_SECONDS", "300") or "300")

    cached = _get_cached_indicator_values(redis_client=redis_client, now=now, max_age_seconds=cache_seconds)
    if cached is None:
        timeout_s = float(os.getenv("CRITICAL_FETCH_TIMEOUT_SECONDS", "4") or "4")

        vix, vix_err = None, "timeout"
        wti, wti_err = None, "timeout"

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fut_vix = ex.submit(fetch_quote_yfinance, "^VIX")
            fut_wti = ex.submit(fetch_quote_yfinance, "CL=F")
            try:
                vix, vix_err = fut_vix.result(timeout=timeout_s)
            except Exception:
                vix, vix_err = None, "timeout"
            try:
                wti, wti_err = fut_wti.result(timeout=timeout_s)
            except Exception:
                wti, wti_err = None, "timeout"
        cached = {
            "^VIX": {"value": vix, "error": vix_err},
            "CL=F": {"value": wti, "error": wti_err},
        }
        _set_cached_indicator_values(redis_client=redis_client, now=now, values=cached, ttl_seconds=cache_seconds)

    vix = _safe_float((cached.get("^VIX") or {}).get("value"))
    vix_err = (cached.get("^VIX") or {}).get("error")
    wti = _safe_float((cached.get("CL=F") or {}).get("value"))
    wti_err = (cached.get("CL=F") or {}).get("error")

    indicators = [
        {
            "name": "VIX",
            "symbol": "^VIX",
            "value": vix,
            "unit": "index",
            "status": classify_threshold(vix, vix_warn, vix_critical),
            "warn": vix_warn,
            "critical": vix_critical,
            "error": vix_err,
            "guidance": "Higher VIX = higher market stress; consider reducing risk when elevated.",
        },
        {
            "name": "WTI Oil",
            "symbol": "CL=F",
            "value": wti,
            "unit": "USD/bbl",
            "status": classify_threshold(wti, wti_warn, wti_critical),
            "warn": wti_warn,
            "critical": wti_critical,
            "error": wti_err,
            "guidance": "Oil spikes can correlate with inflation/geopolitical risk; use as context.",
        },
    ]

    alerts = read_external_alerts(redis_client, max_items=int(os.getenv("CRITICAL_ALERTS_MAX", "8")))

    # Overall status = worst of indicators/alerts
    worst = "ok"
    rank = {"ok": 0, "unknown": 1, "warning": 2, "critical": 3}
    for ind in indicators:
        st = ind.get("status") or "unknown"
        if rank.get(st, 1) > rank.get(worst, 0):
            worst = st
    for a in alerts:
        sev = (a.get("severity") or "info").lower()
        sev_map = {"info": "ok", "warning": "warning", "critical": "critical"}
        st = sev_map.get(sev, "unknown")
        if rank.get(st, 1) > rank.get(worst, 0):
            worst = st

    return {
        "generated_at": now.strftime("%I:%M:%S %p"),
        "overall": worst,
        "indicators": indicators,
        "alerts": alerts,
        "notes": "Indicators/alerts are informational only; verify sources before acting.",
    }
