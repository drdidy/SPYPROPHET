from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from api.deps import get_cache
from api.market_data import fetch_spy_spot_snapshot
from api.structure import compute_structure_projection, fetch_spy_hourly_bars

router = APIRouter(prefix="/chart", tags=["chart"])
logger = logging.getLogger("spyprophet.api.chart")


@router.get("/spy")
def spy_chart(
    period: str = Query(default="5d", description="Yahoo period: 5d / 10d / 1mo"),
):
    """Hourly SPY OHLCV + the four projected primary lines.

    The /chart page renders both as a single decision map: candles +
    line overlay so structure shows up against price.
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    bars = cache.get_or_compute(
        f"chart:bars:{period}",
        lambda: fetch_spy_hourly_bars(period=period),
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
