from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_cache
from api.structure import fetch_spy_hourly_dataframe

router = APIRouter(prefix="/replay", tags=["replay"])
logger = logging.getLogger("spyprophet.api.replay")


@router.get("/spy")
def replay_session(
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="Trading day to replay (YYYY-MM-DD). Defaults to the most recent weekday.",
    ),
):
    """Return a prior session's RTH bars + the structure lines that
    would have been projected from the day-before pivots.

    The /replay page steps bar-by-bar; the API just hands over the full
    session up front and the page hides future bars locally."""
    cache = get_cache()
    df = cache.get_or_compute(
        "replay:spy_hourly",
        lambda: fetch_spy_hourly_dataframe(period="30d"),
        ttl=300.0,
    )
    if df.empty:
        raise HTTPException(status_code=502, detail="Hourly data unavailable.")

    try:
        from app import (
            build_primary_lines,
            filter_rth_session,
            find_high_pivot,
            find_low_pivot,
            project_lines,
        )
    except Exception as exc:
        logger.warning("replay imports failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Replay engine unavailable.") from exc

    target_day = _resolve_replay_day(df, date_str)
    if target_day is None:
        raise HTTPException(status_code=404, detail="No replay-eligible trading days available.")

    rth = filter_rth_session(df, target_day)
    if rth.empty:
        raise HTTPException(
            status_code=404, detail=f"No RTH data found for {target_day.isoformat()}."
        )

    pivot_day = _previous_trading_day(df, target_day)
    if pivot_day is None:
        raise HTTPException(
            status_code=404,
            detail="No prior session available to anchor structure lines from.",
        )
    pivot_rth = filter_rth_session(df, pivot_day)
    if pivot_rth.empty:
        raise HTTPException(
            status_code=404, detail="Pivot day RTH session is empty.",
        )

    high_pivot = find_high_pivot(pivot_rth)
    low_pivot = find_low_pivot(pivot_rth)
    primary_lines = build_primary_lines(high_pivot, low_pivot)

    # Per-bar projection: for each bar in the replay session, project
    # each line to that bar's timestamp. This is what makes the chart
    # show the lines sloping across the day.
    bars = []
    for ts, row in rth.iterrows():
        line_values = {}
        for line in primary_lines:
            try:
                v = line.tradable_value_at(ts)
                if v is not None and v == v:  # not NaN
                    line_values[line.name] = round(float(v), 4)
                else:
                    line_values[line.name] = None
            except Exception:
                line_values[line.name] = None
        bars.append(
            {
                "t": ts.isoformat(),
                "o": _f(row.get("Open")),
                "h": _f(row.get("High")),
                "l": _f(row.get("Low")),
                "c": _f(row.get("Close")),
                "v": _f(row.get("Volume")),
                "lines": line_values,
            }
        )

    end_dt = rth.index[-1]
    projected_at_close = project_lines(primary_lines, end_dt, _f(rth.iloc[-1].get("Close")))
    line_meta = []
    for _, r in projected_at_close.iterrows():
        line_meta.append(
            {
                "name": r.get("name"),
                "label": r.get("level"),
                "kind": r.get("direction"),
            }
        )

    return {
        "session": target_day.isoformat(),
        "pivot_session": pivot_day.isoformat(),
        "bar_count": len(bars),
        "lines": line_meta,
        "bars": bars,
    }


def _resolve_replay_day(df, date_str: str | None) -> date | None:
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date format; expect YYYY-MM-DD.") from exc
    # Most recent trading day (≠ today, since today's session may still be in progress)
    if df.empty:
        return None
    today_ct = datetime.now(ZoneInfo("America/Chicago")).date()
    days = sorted({d for d in df.index.date if d < today_ct}, reverse=True)
    return days[0] if days else None


def _previous_trading_day(df, base: date) -> date | None:
    candidate = base - timedelta(days=1)
    cutoff = base - timedelta(days=10)
    available = {d for d in df.index.date}
    while candidate >= cutoff:
        if candidate in available and candidate.weekday() < 5:
            return candidate
        candidate -= timedelta(days=1)
    return None


def _f(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:
        return None
    return f
