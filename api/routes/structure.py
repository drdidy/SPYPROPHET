from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api.deps import get_cache
from api.market_data import fetch_spy_spot_snapshot
from api.structure import compute_structure_projection

router = APIRouter(prefix="/structure", tags=["structure"])
logger = logging.getLogger("spyprophet.api.structure")


@router.get("/spy")
def spy_structure():
    """Project the four primary structure lines to the current moment.

    Returns ``{pivot_session, as_of, lines, closest_above, closest_below}``.
    Cached 60s alongside the live snapshot so repeated polls hit memory.
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    projection = cache.get_or_compute(
        "structure_projection",
        lambda: compute_structure_projection(spot.get("price")),
        ttl=60.0,
    )
    if not projection:
        raise HTTPException(
            status_code=502,
            detail="SPY hourly data unavailable; cannot project structure.",
        )
    return projection
