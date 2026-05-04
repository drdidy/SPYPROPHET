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

router = APIRouter(tags=["live"])
logger = logging.getLogger("spyprophet.api.live")


@router.get("/live", response_model=LiveSnapshot)
def live_snapshot() -> LiveSnapshot:
    """Composite read for the /live page.

    Phase 1 (this commit): spot, change, VIX regime, watch strikes, decision
    label, last-update timestamp. Phase 2 will compose the briefing helpers
    (lines, signals, bias, trigger, target, guardrails, intel) and populate
    the optional fields on ``LiveSnapshot``.
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    vix = cache.get_or_compute("vix", fetch_vix_snapshot, ttl=30.0)
    watch = watch_strikes(spot.get("price"))

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
        decision_label=_decision_label(spot.get("price")),
        last_update=datetime.now(UTC).isoformat(),
    )


def _decision_label(spot_price: float | None) -> str:
    """Plain-language decision label.

    Intentionally generic until the structure/bias engine is wired in
    phase 2 — does not leak the rule.
    """
    if spot_price is None:
        return "Awaiting market data"
    return "Live read · update on each close"
