"""SPY structure projection — primary lines from prior session pivots,
projected to the current moment and ranked by distance from spot.

This is the API-side wrapper around the existing app.py helpers
(``find_high_pivot``, ``find_low_pivot``, ``build_primary_lines``,
``project_lines``). Trading math stays in app.py (those functions
are the ones drdidy hardened in commits 7276d78 / 9e7b97f / c1de2c6);
we just orchestrate the calls and shape the JSON.

Hourly OHLCV is fetched directly from Yahoo's chart endpoint with
curl_cffi (same TLS-impersonating session market_data.py uses) so we
sidestep the yfinance-vs-cloud-IP bot block.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger("spyprophet.api.structure")


def fetch_spy_hourly_dataframe(period: str = "10d"):
    """Hit query2.finance.yahoo.com directly, return a DataFrame matching
    what ``app.fetch_spy_hourly`` produces: DatetimeIndex localised to
    Central Time, columns Open/High/Low/Close/Volume.
    """
    import pandas as pd

    from api.market_data import _yfinance_session

    session = _yfinance_session()
    url = "https://query2.finance.yahoo.com/v8/finance/chart/SPY"
    params = {"range": period, "interval": "1h"}
    try:
        resp = session.get(url, params=params, timeout=10)
    except Exception as exc:
        logger.warning("Yahoo chart hourly fetch failed: %s", type(exc).__name__)
        return pd.DataFrame()
    if getattr(resp, "status_code", 0) >= 400:
        logger.warning("Yahoo chart hourly returned %s", resp.status_code)
        return pd.DataFrame()
    try:
        payload = resp.json()
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        return pd.DataFrame()

    # Yahoo returns ET timestamps; localise via the meta timezone.
    tz = result.get("meta", {}).get("exchangeTimezoneName") or "America/New_York"
    idx = pd.DatetimeIndex(
        [datetime.fromtimestamp(ts, tz=__import__("zoneinfo").ZoneInfo(tz)) for ts in timestamps]
    )
    df = pd.DataFrame(
        {
            "Open": quote.get("open") or [None] * len(timestamps),
            "High": quote.get("high") or [None] * len(timestamps),
            "Low": quote.get("low") or [None] * len(timestamps),
            "Close": quote.get("close") or [None] * len(timestamps),
            "Volume": quote.get("volume") or [None] * len(timestamps),
        },
        index=idx,
    )
    df = df.dropna(subset=["Close"])
    if df.empty:
        return df
    # Mirror app.ensure_central_index — convert to Central so the RTH
    # filter (08:30–15:00 CT) works.
    try:
        from app import ensure_central_index

        df = ensure_central_index(df)
    except Exception:
        # If app import is unavailable in the call site, do the same
        # conversion ourselves.
        df = df.tz_convert("America/Chicago")
    return df


def _prior_trading_day(now_dt) -> date:
    """Return the most recent weekday strictly before ``now_dt``'s date."""
    import pandas as pd

    cur = pd.Timestamp(now_dt).date()
    candidate = cur - timedelta(days=1)
    while candidate.weekday() >= 5:  # Sat=5, Sun=6
        candidate -= timedelta(days=1)
    return candidate


def compute_structure_projection(spot_price: float | None, now_dt=None) -> dict | None:
    """Project the four primary structure lines to ``now_dt``.

    Returns ``{lines, closest_above, closest_below, pivot_session}``
    or ``None`` if data fetch fails. ``lines`` is a list of dicts:
    ``{name, kind: ascending|descending, projected_value, distance,
    role: trigger_above|target_below|...}``.

    The decision page can pick:
    - ``trigger`` = first line above spot in the upper-zone direction
    - ``target`` = first line below spot in the lower-zone direction
    """
    import pandas as pd

    df = fetch_spy_hourly_dataframe(period="10d")
    if df.empty:
        return None

    try:
        from app import (
            build_primary_lines,
            filter_rth_session,
            find_high_pivot,
            find_low_pivot,
            get_central_tz,
            project_lines,
        )
    except Exception as exc:
        logger.warning("structure imports failed: %s", type(exc).__name__)
        return None

    ct = get_central_tz()
    now = pd.Timestamp(now_dt) if now_dt is not None else pd.Timestamp.now(tz=ct)
    if now.tzinfo is None:
        now = now.tz_localize(ct)
    else:
        now = now.tz_convert(ct)

    # Walk back day by day until we find an RTH session with data.
    pivot_day = _prior_trading_day(now)
    rth = pd.DataFrame()
    for _ in range(7):
        rth = filter_rth_session(df, pivot_day)
        if not rth.empty:
            break
        pivot_day -= timedelta(days=1)
        while pivot_day.weekday() >= 5:
            pivot_day -= timedelta(days=1)
    if rth.empty:
        return None

    high_pivot = find_high_pivot(rth)
    low_pivot = find_low_pivot(rth)
    lines = build_primary_lines(high_pivot, low_pivot)
    projected = project_lines(lines, now, spot_price)

    if projected.empty:
        return None

    rows: list[dict] = []
    for _, r in projected.iterrows():
        value = r.get("tradable_value")
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(value):
            continue
        distance = (value - spot_price) if spot_price is not None else None
        rows.append(
            {
                "name": r.get("name"),
                "label": r.get("level"),
                "role": r.get("role"),
                "kind": r.get("direction"),
                "zone_type": r.get("zone_type"),
                "projected_value": round(value, 4),
                "distance": round(distance, 4) if distance is not None else None,
            }
        )

    if not rows:
        return None

    above = sorted(
        [r for r in rows if r["distance"] is not None and r["distance"] > 0],
        key=lambda r: r["distance"],
    )
    below = sorted(
        [r for r in rows if r["distance"] is not None and r["distance"] < 0],
        key=lambda r: -r["distance"],
    )

    # Trigger candidates per drdidy's methodology: descending lines only.
    # Ascending lines (and secondaries) are intermediate / target-only.
    desc_above = [r for r in above if r.get("kind") == "descending"]
    desc_below = [r for r in below if r.get("kind") == "descending"]

    return {
        "pivot_session": pivot_day.isoformat(),
        "as_of": now.isoformat(),
        "lines": rows,
        "closest_above": above[0] if above else None,
        "closest_below": below[0] if below else None,
        "closest_descending_above": desc_above[0] if desc_above else None,
        "closest_descending_below": desc_below[0] if desc_below else None,
    }
