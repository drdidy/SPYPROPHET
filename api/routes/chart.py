from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Query

from api.deps import get_cache
from api.market_data import fetch_spy_spot_snapshot
from api.structure import (
    _prior_trading_day,
    compute_structure_projection,
    fetch_spy_hourly_dataframe,
)

router = APIRouter(prefix="/chart", tags=["chart"])
logger = logging.getLogger("spyprophet.api.chart")


@router.get("/spy")
def spy_chart(
    period: str = Query(default="5d", description="Yahoo period: 5d / 10d / 1mo"),
):
    """Hourly SPY OHLCV with per-bar projected primary line values.

    Each bar carries a ``lines: {UA, UD, LA, LD}`` map of the line value
    AT THAT BAR'S TIMESTAMP, so the /chart page can draw the structure
    lines sloping naturally across the timeline (anchor + slope × hours).
    Same per-bar projection the /replay endpoint uses.
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    bars = cache.get_or_compute(
        f"chart:bars_with_lines:{period}",
        lambda: _bars_with_lines(period=period),
        ttl=60.0,
    )
    structure = cache.get_or_compute(
        "structure_projection",
        lambda: compute_structure_projection(spot.get("price")),
        ttl=60.0,
    )

    return {
        "period": period,
        "spot_price": spot.get("price"),
        "bars": bars,
        "structure": structure,
    }


def _bars_with_lines(period: str = "5d") -> list[dict]:
    """Fetch hourly bars and project each of the four primary lines to
    every bar's timestamp using the most recent prior session pivots."""
    df = fetch_spy_hourly_dataframe(period=period)
    if df.empty:
        return []

    try:
        from app import (
            build_primary_lines,
            filter_rth_session,
            find_high_pivot,
            find_low_pivot,
        )
    except Exception as exc:
        logger.warning("chart imports failed: %s", type(exc).__name__)
        return []

    # Use the most recent completed RTH session as pivot anchor.
    last_ts = df.index[-1]
    pivot_day = _prior_trading_day(last_ts)
    rth = None
    for _ in range(7):
        rth = filter_rth_session(df, pivot_day)
        if rth is not None and not rth.empty:
            break
        pivot_day -= timedelta(days=1)
        while pivot_day.weekday() >= 5:
            pivot_day -= timedelta(days=1)
    if rth is None or rth.empty:
        return _bars_without_lines(df)

    high_pivot = find_high_pivot(rth)
    low_pivot = find_low_pivot(rth)
    primary = build_primary_lines(high_pivot, low_pivot)

    out: list[dict] = []
    for ts, row in df.iterrows():
        lines = {}
        for line in primary:
            try:
                v = line.tradable_value_at(ts)
                if v is not None and v == v:
                    lines[line.name] = round(float(v), 4)
                else:
                    lines[line.name] = None
            except Exception:
                lines[line.name] = None
        out.append(
            {
                "t": ts.isoformat(),
                "o": _f(row.get("Open")),
                "h": _f(row.get("High")),
                "l": _f(row.get("Low")),
                "c": _f(row.get("Close")),
                "v": _f(row.get("Volume")),
                "lines": lines,
            }
        )
    return out


def _bars_without_lines(df) -> list[dict]:
    out: list[dict] = []
    for ts, row in df.iterrows():
        out.append(
            {
                "t": ts.isoformat(),
                "o": _f(row.get("Open")),
                "h": _f(row.get("High")),
                "l": _f(row.get("Low")),
                "c": _f(row.get("Close")),
                "v": _f(row.get("Volume")),
                "lines": {},
            }
        )
    return out


def _f(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:
        return None
    return f
