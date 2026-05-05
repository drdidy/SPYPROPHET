from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_cache
from api.market_data import fetch_spy_spot_snapshot

router = APIRouter(prefix="/intel", tags=["intel"])
logger = logging.getLogger("spyprophet.api.intel")


@router.get("/spy")
def spy_intel(
    expiration: str = Query(
        default_factory=lambda: date.today().isoformat(),
        description="ISO date used to scope the flow alerts (defaults to today / 0DTE).",
    ),
):
    """UnusualWhales-sourced SPY intel: dark-pool prints, GEX walls,
    flow alerts, recent flow, market tide, net-premium ticks, options
    volume, IV, near-strike Greeks, fresh news.

    Same orchestration as the Streamlit External Context cards. Cached
    90s server-side — UW data updates intraday but we don't need to
    hammer the API.
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)

    cache_key = f"intel:{expiration}"

    def _compute():
        return _gather_intel(spot.get("price"), expiration)

    result = cache.get_or_compute(cache_key, _compute, ttl=90.0)
    if not result:
        raise HTTPException(
            status_code=502,
            detail="UnusualWhales intel unavailable — check UNUSUAL_WHALES_API_KEY.",
        )
    return result


def _gather_intel(spot_price: float | None, expiration: str) -> dict | None:
    try:
        import pandas as pd

        from app import (
            fetch_unusual_whales_intelligence,
            get_central_tz,
        )
    except Exception as exc:
        logger.warning("intel imports failed: %s", type(exc).__name__)
        return None

    try:
        ct = get_central_tz()
        now_ct = pd.Timestamp.now(tz=ct)
        payload, status = fetch_unusual_whales_intelligence(
            expiration_date=expiration,
            latest_price=spot_price,
            now_ct=now_ct,
        )
    except Exception as exc:
        logger.warning("intel fetch failed: %s", type(exc).__name__)
        return None

    return {
        "available": payload is not None,
        "as_of": now_ct.isoformat(),
        "expiration": expiration,
        "status": _status_to_dict(status),
        "data": payload,
    }


def _status_to_dict(status) -> dict:
    if status is None:
        return {}
    if isinstance(status, dict):
        return status
    return {
        "name": getattr(status, "name", None),
        "status": getattr(status, "status", None),
        "detail": getattr(status, "detail", None),
        "as_of": (
            status.as_of.isoformat()
            if hasattr(status, "as_of") and status.as_of is not None and hasattr(status.as_of, "isoformat")
            else None
        ),
        "url": getattr(status, "url", None),
    }
