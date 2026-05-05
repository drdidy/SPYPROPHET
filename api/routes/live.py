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
    prior trading session's pivots, and selects the active trigger and
    target according to drdidy's methodology:

    - **Descending lines (UD, LD)** are the only trigger candidates.
      Ascending and secondary lines are intermediate / target-only.
    - The active trigger is the descending line closest to spot
      (smallest absolute distance). Side determines signal direction:
      above spot → PUT setup, below spot → CALL setup.
    - Target = closest line on the *opposite* side from the trigger
      (any kind — ascending lines are valid as targets).
    - Stop sits on the wrong side of the trigger with a small buffer.

    Bias / signal-detection / wait-gate engine still falls back to page
    placeholders for now.
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
        desc_above = structure.get("closest_descending_above")
        desc_below = structure.get("closest_descending_below")

        # Pick the descending line closer to spot in absolute distance.
        active_setup = _select_active_setup(desc_above, desc_below)

        if active_setup:
            trigger_line, signal_direction = active_setup
            # Target = opposite side, any kind.
            target_line = (
                structure.get("closest_below")
                if signal_direction == "PUT"
                else structure.get("closest_above")
            )

            trigger = {
                "name": trigger_line.get("label") or trigger_line.get("name"),
                "line_code": trigger_line.get("name"),
                "value": trigger_line.get("projected_value"),
                "distance": trigger_line.get("distance"),
                "kind": trigger_line.get("kind"),
                "setup": signal_direction,
            }

            stop_buffer = 0.20
            stop_value = trigger_line.get("projected_value")
            if stop_value is not None:
                stop = round(
                    stop_value
                    + (stop_buffer if signal_direction == "PUT" else -stop_buffer),
                    2,
                )

            if target_line:
                tval = target_line.get("projected_value")
                trig_v = trigger_line.get("projected_value")
                rr = None
                if (
                    tval is not None
                    and trig_v is not None
                    and stop is not None
                ):
                    risk = abs(stop - trig_v)
                    reward = abs(tval - trig_v)
                    rr = round(reward / risk, 2) if risk > 0 else None
                target = {
                    "name": target_line.get("label") or target_line.get("name"),
                    "line_code": target_line.get("name"),
                    "value": tval,
                    "distance": target_line.get("distance"),
                    "kind": target_line.get("kind"),
                    "rr": rr,
                }

            verb = "below" if signal_direction == "PUT" else "above"
            decision_label = (
                f"{signal_direction} setup · trigger close {verb} "
                f"{trigger_line['projected_value']:.2f}"
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


def _select_active_setup(
    desc_above: dict | None, desc_below: dict | None
) -> tuple[dict, str] | None:
    """Return ``(trigger_line, signal_direction)`` for whichever
    descending line is closer to spot. PUT setup if the trigger is
    above, CALL if below."""
    candidates: list[tuple[dict, str, float]] = []
    if desc_above and desc_above.get("distance") is not None:
        candidates.append((desc_above, "PUT", abs(desc_above["distance"])))
    if desc_below and desc_below.get("distance") is not None:
        candidates.append((desc_below, "CALL", abs(desc_below["distance"])))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[2])
    line, direction, _ = candidates[0]
    return line, direction


def _decision_label(spot_price: float | None) -> str:
    if spot_price is None:
        return "Awaiting market data"
    return "Live read · update on each close"
