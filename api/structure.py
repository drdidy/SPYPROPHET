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


def fetch_spy_hourly_bars(period: str = "10d") -> list[dict]:
    """Public hourly OHLCV for the /chart page. Returns a list of dicts
    in chronological order, each ``{t (ISO Central Time), o, h, l, c, v}``.
    Backed by the same curl_cffi-impersonated chart endpoint."""
    df = fetch_spy_hourly_dataframe(period=period)
    if df.empty:
        return []
    out: list[dict] = []
    for ts, row in df.iterrows():
        out.append(
            {
                "t": ts.isoformat(),
                "o": _coerce_float(row.get("Open")),
                "h": _coerce_float(row.get("High")),
                "l": _coerce_float(row.get("Low")),
                "c": _coerce_float(row.get("Close")),
                "v": _coerce_float(row.get("Volume")),
            }
        )
    return out


def _coerce_float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


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
    """Project the four primary structure lines to **today's 9am CT**.

    The trigger price is the line's value at 09:00 Central of the
    current trading day — that's drdidy's reference point, *static for
    the day* once the session opens. We do not project to the rolling
    "now" because the trigger needs to be a fixed level price can
    touch, not a constantly-shifting target.

    Returns ``{lines, closest_above, closest_below, closest_descending_*,
    pivot_session, projection_time, as_of}`` or ``None`` if data fetch
    fails.
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
            get_structure_projection_time,
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

    # The projection target is *today's* 9am CT — not now. Trigger
    # prices stay locked once the session is open.
    projection_time = get_structure_projection_time(now, hour=9, minute=0)

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
    # Project to today's 9am CT — that's the trigger reference time.
    projected = project_lines(lines, projection_time, spot_price)

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
        "projection_time": projection_time.isoformat(),
        "lines": rows,
        "closest_above": above[0] if above else None,
        "closest_below": below[0] if below else None,
        "closest_descending_above": desc_above[0] if desc_above else None,
        "closest_descending_below": desc_below[0] if desc_below else None,
    }


def compute_live_state(spot_price: float | None, now_dt=None) -> dict | None:
    """End-to-end live state — projection + bias + active signals + guardrails.

    Wraps the same prior-session pivot path as ``compute_structure_projection``
    but additionally:

    - calls ``determine_preopen_bias`` for the bias snapshot
    - calls ``detect_rejection_signals`` against today's candles, restricted
      to the **descending** primary lines (UD, LD) per drdidy's methodology
      — ascending lines are intermediate / target-only
    - grades the most recent signal via ``score_signal_quality`` and assembles
      a ``DecisionState`` with guardrails (chase / retest / structure /
      daily-loss) so the live page can render real wait-gate states

    Returns ``None`` if hourly data is unavailable. Otherwise returns:

    ``{pivot_session, as_of, lines, closest_*, bias, signals, latest_signal,
       decision, today_signal_count}``
    """
    import pandas as pd

    df = fetch_spy_hourly_dataframe(period="10d")
    if df.empty:
        return None

    try:
        from app import (
            build_decision_state,
            build_primary_lines,
            detect_rejection_signals,
            determine_preopen_bias,
            filter_rth_session,
            find_high_pivot,
            find_low_pivot,
            get_central_tz,
            get_structure_projection_time,
            score_signal_quality,
        )
    except Exception as exc:
        logger.warning("live-state imports failed: %s", type(exc).__name__)
        return None

    ct = get_central_tz()
    now = pd.Timestamp(now_dt) if now_dt is not None else pd.Timestamp.now(tz=ct)
    if now.tzinfo is None:
        now = now.tz_localize(ct)
    else:
        now = now.tz_convert(ct)

    # All projection / bias / trigger evaluation happens at today's 9am CT.
    projection_time = get_structure_projection_time(now, hour=9, minute=0)

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
    primary_lines = build_primary_lines(high_pivot, low_pivot)
    descending_lines = [line for line in primary_lines if line.direction == "descending"]

    # Today's candles for signal detection. If the API runs before the
    # session opens, today's RTH frame is empty — fall back to all
    # candles since the most recent open so the engine can still see
    # premarket structure.
    today_rth = filter_rth_session(df, now.date())
    signal_frame = today_rth if not today_rth.empty else df[df.index.date == now.date()].sort_index()

    # Detect signals only against descending lines per methodology.
    signals = detect_rejection_signals(signal_frame, descending_lines, [])
    latest_signal = signals[-1] if signals else None

    # Bias is evaluated against today's 9am-projected line values so it
    # tracks where current price sits relative to the locked trigger
    # structure rather than a moving target.
    bias = determine_preopen_bias(primary_lines, spot_price or 0.0, projection_time)

    quality = score_signal_quality(latest_signal) if latest_signal is not None else None
    latest_candle_row = signal_frame.iloc[-1] if not signal_frame.empty else None
    decision = build_decision_state(
        latest_signal,
        primary_lines,
        spot_price,
        now,
        latest_candle_row,
        signals_today=signals,
    )

    projection = compute_structure_projection(spot_price, now_dt=now)

    return {
        **(projection or {}),
        "bias": _bias_to_dict(bias, spot_price),
        "signals": [_signal_to_dict(s) for s in signals],
        "latest_signal": _signal_to_dict(latest_signal) if latest_signal else None,
        "signal_quality": _quality_to_dict(quality) if quality else None,
        "decision": _decision_to_dict(decision) if decision else None,
        "today_signal_count": len(signals),
    }


def _bias_to_dict(bias, spot_price) -> dict:
    """Translate BiasState → JSON. Direction key matches the page's
    DirectionGlyph component (call/put/neutral)."""
    label_map = {
        "BULLISH": "Bullish",
        "BEARISH": "Bearish",
        "NEUTRAL": "Neutral",
        "REGULAR_SESSION": "Active",
        "UNKNOWN": "Calibrating",
    }
    direction_map = {
        "BULLISH": "call",
        "BEARISH": "put",
        "NEUTRAL": "neutral",
        "REGULAR_SESSION": "neutral",
        "UNKNOWN": "neutral",
    }
    return {
        "label": label_map.get(bias.bias, "Calibrating"),
        "direction": direction_map.get(bias.bias, "neutral"),
        "code": bias.bias,
        "explanation": bias.explanation,
        "score": bias.strength_score,
        "watched_call_lines": list(bias.watched_call_lines or []),
        "watched_put_lines": list(bias.watched_put_lines or []),
        "primary_line": bias.primary_line,
        "take_profit_line": bias.final_take_profit_line,
    }


def _signal_to_dict(signal) -> dict | None:
    if signal is None:
        return None
    import pandas as pd

    def _ts(v):
        return v.isoformat() if isinstance(v, pd.Timestamp) and not pd.isna(v) else None

    def _f(v):
        try:
            f = float(v)
            return None if (pd.isna(f)) else f
        except (TypeError, ValueError):
            return None

    return {
        "signal_id": signal.signal_id,
        "signal_type": signal.signal_type,
        "status": signal.status,
        "line_name": signal.line_name,
        "rejection_time": _ts(signal.rejection_time),
        "entry_time": _ts(signal.entry_time),
        "entry_price": _f(signal.entry_price),
        "stop_price": _f(signal.stop_price),
        "target_line_name": signal.target_line_name,
        "target_price": _f(signal.target_price),
        "rr_ratio": _f(signal.rr_ratio),
        "explanation": signal.explanation,
    }


def _quality_to_dict(q) -> dict:
    return {
        "grade": q.grade,
        "score": q.score,
        "action_label": q.action_label,
        "explanation": q.explanation,
        "warnings": list(q.warnings or []),
        "strengths": list(q.strengths or []),
    }


def _decision_to_dict(d) -> dict:
    g = d.guardrail_state
    return {
        "final_decision": d.final_decision,
        "explanation": d.final_explanation,
        "guardrails": {
            "chase_status": g.chase_status,
            "chase_warning": g.chase_warning,
            "retest_status": g.retest_status,
            "retest_line_name": g.retest_line_name,
            "structure_status": g.structure_status,
            "structure_warning": g.structure_warning,
            "daily_action": g.daily_action,
            "explanation": g.explanation,
        },
    }
