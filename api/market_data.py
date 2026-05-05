"""Thin, Streamlit-free wrappers around yfinance for the API process.

We re-implement the small surface the live endpoint needs (spot snapshot,
VIX read) instead of importing the @st.cache_data-decorated versions from
``app.py`` — that path works but emits noisy warnings and pins us to
Streamlit's runtime caching. The math we depend on (signal engine, line
projection) still lives in app.py; this file is only the data fetch.
"""
from __future__ import annotations

import logging
import math
from threading import Lock

logger = logging.getLogger("spyprophet.api.market_data")

# Yahoo Finance rejects requests from cloud-IP ranges (Render, AWS, GCP,
# etc.) when they look like default Python requests; the response is HTML
# error page, yfinance then logs "possibly delisted; no price data found".
# Fix: hand yfinance a session with browser-realistic headers.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
_session_lock = Lock()
_yf_session = None


def _yfinance_session():
    """Build (and memoize) a requests.Session with browser headers."""
    global _yf_session
    if _yf_session is not None:
        return _yf_session
    with _session_lock:
        if _yf_session is not None:
            return _yf_session
        import requests

        s = requests.Session()
        s.headers.update(_BROWSER_HEADERS)
        _yf_session = s
    return _yf_session


def _normalize_history_columns(df):
    import pandas as pd

    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(c).strip() for c in out.columns]
    return out


def fetch_tastytrade_market_quote(symbol: str) -> dict | None:
    """Pull a real-time quote from Tastytrade's REST market-data endpoint.

    Returns a dict with the raw fields Tastytrade hands back (last, bid,
    ask, prev-close, etc.) or None if the call fails or Tastytrade isn't
    configured. Used as the primary path for SPY/VIX so we don't depend
    on yfinance from cloud egress IPs.
    """
    try:
        from api.deps import get_tastytrade_provider

        provider = get_tastytrade_provider()
    except Exception as exc:
        logger.debug("Tastytrade provider unavailable: %s", type(exc).__name__)
        return None
    if provider is None:
        return None

    try:
        token = provider.get_access_token()
    except Exception as exc:
        logger.warning("Tastytrade auth failed: %s", type(exc).__name__)
        return None
    if not token:
        return None

    try:
        import requests

        headers = {**provider.api_headers, "Authorization": f"Bearer {token}"}
        # Tastytrade represents indices with a "/" prefix on some symbols;
        # for VIX they expose "VIX" directly, for SPY just "SPY".
        url_symbol = symbol.lstrip("^")
        r = requests.get(
            f"{provider.base}/market-data/{url_symbol}",
            headers=headers,
            timeout=5,
        )
        if r.status_code >= 400:
            logger.warning(
                "Tastytrade market-data %s returned %s", symbol, r.status_code
            )
            return None
        payload = r.json()
    except Exception as exc:
        logger.warning("Tastytrade market-data %s failed: %s", symbol, type(exc).__name__)
        return None

    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and "items" in data:
        items = data.get("items") or []
        return items[0] if items else None
    return data


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def fetch_spy_spot_snapshot() -> dict:
    """Return the latest SPY price plus the change vs prior session close.

    Order of preference: Tastytrade REST (real-time, reliable from cloud
    IPs) → yfinance (browser-headed session, fallback). All None on
    cascading failure.
    """
    tt = fetch_tastytrade_market_quote("SPY")
    if tt:
        last = _safe_float(tt.get("last") or tt.get("mark"))
        bid = _safe_float(tt.get("bid"))
        ask = _safe_float(tt.get("ask"))
        prev_close = _safe_float(
            tt.get("prev-close") or tt.get("previous-close") or tt.get("close")
        )
        if last is None and bid is not None and ask is not None:
            last = (bid + ask) / 2
        if last is not None:
            change = (last - prev_close) if prev_close is not None else None
            change_pct = (change / prev_close * 100) if prev_close else None
            return {
                "price": _clean(last),
                "change": _clean(change),
                "change_pct": _clean(change_pct),
            }
        logger.debug("Tastytrade SPY quote present but no price; falling back")

    return _yfinance_spy_snapshot()


def _yfinance_spy_snapshot() -> dict:
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed; SPY snapshot unavailable")
        return {"price": None, "change": None, "change_pct": None}

    try:
        df = yf.Ticker("SPY", session=_yfinance_session()).history(
            period="5d", interval="1d", auto_adjust=False
        )
    except Exception as exc:
        logger.warning("yfinance SPY fetch failed: %s", type(exc).__name__)
        return {"price": None, "change": None, "change_pct": None}

    df = _normalize_history_columns(df)
    if df.empty or "Close" not in df.columns or len(df) < 1:
        return {"price": None, "change": None, "change_pct": None}

    closes = df["Close"].dropna()
    if closes.empty:
        return {"price": None, "change": None, "change_pct": None}

    price = float(closes.iloc[-1])
    if len(closes) >= 2:
        prev = float(closes.iloc[-2])
        change = price - prev
        change_pct = (change / prev) * 100 if prev else None
    else:
        change = None
        change_pct = None

    return {
        "price": _clean(price),
        "change": _clean(change),
        "change_pct": _clean(change_pct),
    }


def fetch_vix_snapshot() -> dict:
    """Return latest VIX value + a regime label/tone.

    Tastytrade primary, yfinance fallback (same rationale as SPY).
    """
    tt = fetch_tastytrade_market_quote("VIX")
    if tt:
        last = _safe_float(tt.get("last") or tt.get("mark"))
        if last is None:
            bid = _safe_float(tt.get("bid"))
            ask = _safe_float(tt.get("ask"))
            if bid is not None and ask is not None:
                last = (bid + ask) / 2
        if last is not None:
            regime, tone = classify_vix(last)
            return {"value": _clean(last), "regime": regime, "regime_tone": tone}
        logger.debug("Tastytrade VIX quote present but no price; falling back")

    return _yfinance_vix_snapshot()


def _yfinance_vix_snapshot() -> dict:
    try:
        import yfinance as yf
    except ImportError:
        return {"value": None, "regime": None, "regime_tone": None}

    try:
        df = yf.Ticker("^VIX", session=_yfinance_session()).history(
            period="5d", interval="15m", auto_adjust=False
        )
    except Exception as exc:
        logger.warning("yfinance VIX fetch failed: %s", type(exc).__name__)
        return {"value": None, "regime": None, "regime_tone": None}

    df = _normalize_history_columns(df)
    if df.empty or "Close" not in df.columns:
        return {"value": None, "regime": None, "regime_tone": None}

    closes = df["Close"].dropna()
    if closes.empty:
        return {"value": None, "regime": None, "regime_tone": None}

    value = float(closes.iloc[-1])
    regime, tone = classify_vix(value)
    return {"value": _clean(value), "regime": regime, "regime_tone": tone}


def classify_vix(value: float) -> tuple[str, str]:
    """Same thresholds as app.py's classify_vix, returned as (label, tone).

    Tone keys map to the front-end colour palette (green / amber / red).
    """
    if value < 15:
        return "Calm", "green"
    if value < 20:
        return "Moderate", "green"
    if value < 25:
        return "Elevated", "amber"
    if value < 30:
        return "High", "amber"
    return "Extreme", "red"


def watch_strikes(spot_price: float | None, distance: float = 2.0) -> dict:
    """Return suggested OTM call/put strikes around the current spot.

    Same default distance app.py uses (TARGET_OTM_STRIKE_DISTANCE = 2.0).
    """
    if spot_price is None or math.isnan(spot_price):
        return {"call": None, "put": None}
    return {
        "call": int(round(spot_price + distance)),
        "put": int(round(spot_price - distance)),
    }


def _clean(value):
    if value is None:
        return None
    try:
        if math.isnan(value) or math.isinf(value):
            return None
    except (TypeError, ValueError):
        return value
    return float(value)
