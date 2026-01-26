"""RSS-based market news monitor -> Redis critical alerts.

Purpose
-------
You said you don't want to manually watch news all day.
This script runs continuously and:

1) Polls configured RSS/Atom feeds (no scraping of sites)
2) Filters for market-moving keywords and/or your watchlist tickers
3) Writes concise alerts into Redis key `critical_alerts_v1`

The dashboard already reads and displays those alerts.

Configuration (env vars)
------------------------
- NEWS_RSS_URLS: Comma-separated feed URLs (required for useful output)
- NEWS_POLL_SECONDS: Poll interval (default 60)
- NEWS_MAX_ALERTS: Max alerts stored in the list (default 200)
- NEWS_SEEN_TTL_SECONDS: Dedup TTL (default 172800 = 2 days)

Filtering:
- NEWS_KEYWORDS: Comma-separated keywords (optional). If not set, defaults are used.
- WATCHLIST_TICKERS: Comma-separated tickers (optional). If set, tickers boost relevance.

Notes
-----
- We only store: timestamp, severity, title, message, source, url.
- We do NOT store full article text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv

try:
    import redis  # type: ignore
except Exception:
    redis = None

try:
    import psycopg2  # type: ignore
except Exception:
    psycopg2 = None

import urllib.request
import xml.etree.ElementTree as ET


ALERTS_KEY = "critical_alerts_v1"
SEEN_KEY_PREFIX = "critical_alert_seen_v1:"


DEFAULT_KEYWORDS = [
    # Macro / rates
    "fed",
    "fomc",
    "powell",
    "interest rate",
    "rate hike",
    "rate cut",
    "cpi",
    "inflation",
    "jobs report",
    "nonfarm",
    "unemployment",
    "yield",
    "treasury",
    # Market stress / risk
    "bank",
    "liquidity",
    "default",
    "downgrade",
    "bankrupt",
    "halted",
    "trading halt",
    "sec",
    "investigation",
    "recall",
    # Geopolitical / energy
    "sanction",
    "war",
    "missile",
    "invasion",
    "strike",
    "opec",
    "oil",
    "gas",
]


# Weighted keyword buckets. Keep these high-signal and broad.
KEYWORD_BUCKETS: List[Tuple[str, float, List[str]]] = [
    (
        "macro",
        5.0,
        [
            "fed",
            "fomc",
            "powell",
            "interest rate",
            "rate hike",
            "rate cut",
            "cpi",
            "inflation",
            "ppi",
            "jobs report",
            "nonfarm",
            "unemployment",
            "yield",
            "treasury",
        ],
    ),
    (
        "regulatory",
        4.0,
        [
            "sec",
            "doj",
            "charges",
            "investigation",
            "lawsuit",
            "settlement",
            "antitrust",
            "recall",
        ],
    ),
    (
        "stress",
        4.0,
        [
            "bank",
            "liquidity",
            "default",
            "downgrade",
            "bankrupt",
            "halted",
            "trading halt",
        ],
    ),
    (
        "geopolitical_energy",
        3.0,
        [
            "sanction",
            "war",
            "missile",
            "invasion",
            "strike",
            "opec",
            "oil",
            "gas",
        ],
    ),
]


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\n")
    return h.hexdigest()[:24]


def _http_get(url: str, *, timeout: float = 8.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TradeAgentNewsMonitor/1.0 (+https://localhost)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _first(el: ET.Element, paths: Iterable[str]) -> Optional[ET.Element]:
    for p in paths:
        found = el.find(p)
        if found is not None:
            return found
    return None


def parse_feed_items(xml_bytes: bytes) -> List[Dict[str, str]]:
    """Return a list of {title, link, published, source} from RSS/Atom."""
    items: List[Dict[str, str]] = []
    root = ET.fromstring(xml_bytes)

    # RSS: <rss><channel><item>...</item>
    channel = root.find("channel")
    if channel is not None:
        source = _text(channel.find("title"))
        for it in channel.findall("item"):
            title = _text(_first(it, ["title"]))
            link = _text(_first(it, ["link"]))
            pub = _text(_first(it, ["pubDate", "date"]))
            if title and link:
                items.append({"title": title, "link": link, "published": pub, "source": source or "rss"})
        return items

    # Atom: <feed><entry>...</entry>
    # Namespaces vary; handle common Atom namespace.
    ns = {"a": "http://www.w3.org/2005/Atom"}
    feed_title = root.find("a:title", ns)
    source = _text(feed_title) or "atom"
    for entry in root.findall("a:entry", ns):
        title = _text(entry.find("a:title", ns))
        link_el = entry.find("a:link", ns)
        link = ""
        if link_el is not None:
            link = (link_el.attrib.get("href") or "").strip()
        pub = _text(entry.find("a:updated", ns)) or _text(entry.find("a:published", ns))
        if title and link:
            items.append({"title": title, "link": link, "published": pub, "source": source})
    return items


def score_item(title: str, *, keywords: List[str], tickers: List[str]) -> Tuple[float, List[str], List[str]]:
    """Return (score, matched_reasons, matched_tickers)."""
    t = title.lower()
    reasons: List[str] = []
    matched_tickers: List[str] = []
    score = 0.0

    # Weighted, high-signal buckets first.
    for bucket, weight, bucket_keywords in KEYWORD_BUCKETS:
        for kw in bucket_keywords:
            if kw in t:
                score += weight
                reasons.append(f"{bucket}:{kw}")

    # Optional extra keywords (user-configured). Lower weight.
    for kw in keywords:
        k = kw.lower()
        if not k:
            continue
        if k in t:
            score += 1.5
            reasons.append(f"keyword:{kw}")

    for tk in tickers:
        # match whole-word-ish to reduce false positives
        token = tk.strip().upper()
        if not token:
            continue
        if f" {token.lower()} " in f" {t} ":
            score += 6.0
            reasons.append(f"ticker:{token}")
            if token not in matched_tickers:
                matched_tickers.append(token)

    # Extra bumps for obviously urgent language
    urgent_terms = ["breaking", "emergency", "explosion", "halt", "lawsuit", "charges", "bankrupt"]
    for ut in urgent_terms:
        if ut in t:
            score += 2.0
            reasons.append(f"urgent:{ut}")

    return score, reasons, matched_tickers


def severity_from_score(score: float) -> str:
    if score >= 7:
        return "critical"
    if score >= 4:
        return "warning"
    return "info"


def get_db_connection():
    if psycopg2 is None:
        return None
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "tradeagent"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
    except Exception:
        return None


def load_held_tickers_from_db(*, limit: int = 200) -> List[str]:
    """Best-effort read-only lookup of currently-held tickers."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT ticker
            FROM positions
            WHERE quantity > 0
            ORDER BY ticker
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall() or []
        return [str(r[0]).strip().upper() for r in rows if r and r[0]]
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_redis_connection() -> Any:
    if redis is None:
        return None
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )
        r.ping()
        return r
    except Exception:
        return None


def _append_alert(redis_client: Any, alert: Dict[str, Any], *, max_alerts: int) -> None:
    raw = redis_client.get(ALERTS_KEY)
    alerts: List[Dict[str, Any]] = []
    try:
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                alerts = parsed
    except Exception:
        alerts = []

    alerts.append(alert)
    if len(alerts) > max_alerts:
        alerts = alerts[-max_alerts:]
    redis_client.set(ALERTS_KEY, json.dumps(alerts))


def _seen(redis_client: Any, alert_id: str) -> bool:
    try:
        return redis_client.get(SEEN_KEY_PREFIX + alert_id) == "1"
    except Exception:
        return False


def _mark_seen(redis_client: Any, alert_id: str, ttl_seconds: int) -> None:
    try:
        redis_client.setex(SEEN_KEY_PREFIX + alert_id, max(ttl_seconds, 3600), "1")
    except Exception:
        return


def run_loop() -> int:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

    rss_urls = _split_csv(os.getenv("NEWS_RSS_URLS"))
    poll_seconds = int(os.getenv("NEWS_POLL_SECONDS", "60") or "60")
    max_alerts = int(os.getenv("NEWS_MAX_ALERTS", "200") or "200")
    seen_ttl = int(os.getenv("NEWS_SEEN_TTL_SECONDS", "172800") or "172800")
    min_score = float(os.getenv("NEWS_MIN_SCORE", "3") or "3")
    fetch_timeout = float(os.getenv("NEWS_FETCH_TIMEOUT_SECONDS", "8") or "8")

    # Keep keyword configuration simple: either explicit list, or defaults.
    keywords = _split_csv(os.getenv("NEWS_KEYWORDS")) or DEFAULT_KEYWORDS

    # Tickers = WATCHLIST_TICKERS + (optionally) currently-held tickers from DB.
    tickers = _split_csv(os.getenv("WATCHLIST_TICKERS"))
    use_db_holdings = os.getenv("NEWS_INCLUDE_DB_HOLDINGS", "true").lower() in ("1", "true", "yes")
    if use_db_holdings:
        held = load_held_tickers_from_db()
        for t in held:
            if t and t not in tickers:
                tickers.append(t)

    if not rss_urls:
        print("[news_monitor] NEWS_RSS_URLS is empty. Nothing to poll.")
        print("[news_monitor] Example (good starting feeds):")
        print("  - https://www.sec.gov/rss/news/press.xml")
        print("  - https://www.federalreserve.gov/feeds/press_all.xml")
        return 2

    r = get_redis_connection()
    if not r:
        print("[news_monitor] Redis unavailable. Start Redis and retry.")
        return 3

    print("[news_monitor] running")
    print(f"[news_monitor] urls={len(rss_urls)} poll={poll_seconds}s min_score={min_score} max_alerts={max_alerts} tickers={len(tickers)}")

    while True:
        loop_started = time.time()
        for url in rss_urls:
            try:
                xml_bytes = _http_get(url, timeout=fetch_timeout)
                feed_items = parse_feed_items(xml_bytes)
            except Exception as e:
                print(f"[news_monitor] fetch failed: {url} -> {e}")
                continue

            for it in feed_items[:50]:
                title = (it.get("title") or "").strip()
                link = (it.get("link") or "").strip()
                published = (it.get("published") or "").strip()
                source = (it.get("source") or "").strip() or "feed"
                if not title or not link:
                    continue

                alert_id = _hash_id(source, title, link)
                if _seen(r, alert_id):
                    continue

                score, reasons, matched = score_item(title, keywords=keywords, tickers=tickers)
                if score < min_score:
                    continue

                alert = {
                    "id": alert_id,
                    "ts": published or _now_iso(),
                    "severity": severity_from_score(score),
                    "title": title,
                    "message": f"score={score:.1f}" + (" • " + " • ".join(reasons[:5]) if reasons else ""),
                    "source": source,
                    "url": link,
                }

                if matched:
                    alert["matched"] = matched[:10]

                _append_alert(r, alert, max_alerts=max_alerts)
                _mark_seen(r, alert_id, ttl_seconds=seen_ttl)
                print(f"[news_monitor] alert: {alert['severity']} {title}")

        elapsed = time.time() - loop_started
        sleep_for = max(5, poll_seconds - int(elapsed))
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(run_loop())
