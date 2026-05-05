from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from api.deps import get_cache
from api.market_data import (
    fetch_spy_spot_snapshot,
    fetch_vix_snapshot,
    watch_strikes,
)
from api.schemas import (
    LiveSnapshot,
    SpotSnapshot,
    VixSnapshot,
    WatchStrikes,
)
from api.structure import compute_structure_projection

router = APIRouter(tags=["live"])
logger = logging.getLogger("spyprophet.api.live")


@router.get("/live", response_model=LiveSnapshot)
def live_snapshot() -> LiveSnapshot:
    """Composite read for the /live page.

    Pulls spot + VIX, projects the four primary structure lines from the
    prior trading session's pivots, and selects the closest line above
    spot as the trigger and the closest below as the target. The full
    bias / signal-detection / wait-gate engine is the next phase — for
    now bias and signal stay null and the page falls back to its
    'Calibrating' / 'Awaiting structure read' placeholders.
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    vix = cache.get_or_compute("vix", fetch_vix_snapshot, ttl=30.0)
    watch = watch_strikes(spot.get("price"))

    structure = cache.get_or_compute(
        "structure_projection",
        lambda: compute_structure_projection(spot.get("price")),
        ttl=60.0,
    )

    trigger = None
    target = None
    stop = None
    decision_label = _decision_label(spot.get("price"))

    if structure:
        above = structure.get("closest_above")
        below = structure.get("closest_below")
        spot_price = spot.get("price")

        if above:
            trigger = {
                "name": above.get("label") or above.get("name"),
                "line_code": above.get("name"),
                "value": above.get("projected_value"),
                "distance": above.get("distance"),
                "kind": above.get("kind"),
            }
        if below:
            entry = (
                above.get("projected_value") if above else spot_price
            ) or 0.0
            target_value = below.get("projected_value") or 0.0
            risk = (entry - (spot_price or entry)) if spot_price is not None else 0.0
            reward = (entry - target_value) if target_value else 0.0
            rr = (
                round(abs(reward) / abs(risk), 2)
                if risk and reward
                else None
            )
            target = {
                "name": below.get("label") or below.get("name"),
                "line_code": below.get("name"),
                "value": below.get("projected_value"),
                "distance": below.get("distance"),
                "kind": below.get("kind"),
                "rr": rr,
            }
            # Stop is just below the lower structure line (~0.20 buffer)
            stop = round(target_value - 0.20, 2) if target_value else None

        if above and spot_price is not None:
            decision_label = (
                f"Hold for trigger close above {above['projected_value']:.2f}"
            )

    return LiveSnapshot(
        spot=SpotSnapshot(
            price=spot.get("price"),
            change=spot.get("change"),
            change_pct=spot.get("change_pct"),
        ),
        vix=VixSnapshot(
            value=vix.get("value"),
            regime=vix.get("regime"),
            regime_tone=vix.get("regime_tone"),
        ),
        watch=WatchStrikes(call=watch["call"], put=watch["put"]),
        decision_label=decision_label,
        last_update=datetime.now(UTC).isoformat(),
        trigger=trigger,
        target=target,
        stop=stop,
    )


def _decision_label(spot_price: float | None) -> str:
    if spot_price is None:
        return "Awaiting market data"
    return "Live read · update on each close"
