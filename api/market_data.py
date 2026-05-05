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


def fetch_spy_spot_snapshot() -> dict:
    """Return the latest SPY price plus the change vs prior session close.

    Output keys: ``price`` (float | None), ``change`` (float | None),
    ``change_pct`` (float | None). All None on upstream failure — the API
    response wraps that into a partial snapshot rather than 5xx.
    """
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
    """Return latest VIX value + a regime label/tone."""
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
