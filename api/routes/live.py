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
from api.structure import compute_live_state

router = APIRouter(tags=["live"])
logger = logging.getLogger("spyprophet.api.live")


@router.get("/live", response_model=LiveSnapshot)
def live_snapshot() -> LiveSnapshot:
    """Composite read for the /live page.

    Pulls spot + VIX, computes the full structure projection + bias +
    active signals + decision/guardrails via api.structure.compute_live_state.
    Methodology: descending lines (UD, LD) are the only signal/trigger
    candidates; ascending and secondaries are intermediate / target-only
    (see project_structure_methodology memory).
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    vix = cache.get_or_compute("vix", fetch_vix_snapshot, ttl=30.0)
    watch = watch_strikes(spot.get("price"))

    state = cache.get_or_compute(
        "live_state",
        lambda: compute_live_state(spot.get("price")),
        ttl=45.0,
    )

    # Pull UnusualWhales intel into the same response so the page's
    # Intel grid renders without a second client-side fetch.
    intel_payload = cache.get_or_compute(
        "intel:default",
        lambda: _fetch_intel_for_live(spot.get("price")),
        ttl=90.0,
    )
    intel_cards = _build_intel_cards(intel_payload)

    trigger = None
    target = None
    stop = None
    bias_payload = None
    signal_payload = None
    guardrails_payload = None
    decision_payload = None
    grade = None
    action = None
    decision_label = _decision_label(spot.get("price"))

    if state:
        # Trigger / target — descending-only, side flips by setup
        desc_above = state.get("closest_descending_above")
        desc_below = state.get("closest_descending_below")
        active_setup = _select_active_setup(desc_above, desc_below)

        if active_setup:
            trigger_line, signal_direction = active_setup
            target_line = (
                state.get("closest_below")
                if signal_direction == "PUT"
                else state.get("closest_above")
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
            tval = trigger_line.get("projected_value")
            if tval is not None:
                stop = round(
                    tval + (stop_buffer if signal_direction == "PUT" else -stop_buffer),
                    2,
                )

            if target_line:
                target_value = target_line.get("projected_value")
                # R:R is only meaningful when a real signal has fired —
                # the structural stop buffer (0.20) overstates R:R into
                # 15-20:1 territory. When no confirmed signal exists,
                # leave R:R null so the page shows "—" rather than a
                # misleading number.
                rr = None
                latest_signal = state.get("latest_signal") or {}
                if (
                    latest_signal.get("status") == "CONFIRMED"
                    and isinstance(latest_signal.get("rr_ratio"), int | float)
                    and latest_signal.get("rr_ratio") > 0
                ):
                    rr = round(float(latest_signal["rr_ratio"]), 2)
                target = {
                    "name": target_line.get("label") or target_line.get("name"),
                    "line_code": target_line.get("name"),
                    "value": target_value,
                    "distance": target_line.get("distance"),
                    "kind": target_line.get("kind"),
                    "rr": rr,
                }
            verb = "below" if signal_direction == "PUT" else "above"
            decision_label = (
                f"{signal_direction} setup · trigger close {verb} "
                f"{tval:.2f}"
            )

        # Bias
        bias_payload = state.get("bias")

        # Latest signal — present a short label for the page
        latest_signal = state.get("latest_signal")
        if latest_signal:
            status = latest_signal.get("status", "")
            sig_type = latest_signal.get("signal_type", "")
            line_name = latest_signal.get("line_name", "")
            if status == "CONFIRMED":
                signal_label = f"{sig_type} confirmed on {line_name}"
            elif status == "PENDING_CONFIRMATION":
                signal_label = f"{sig_type} pending on {line_name}"
            else:
                signal_label = f"{sig_type} {status.lower()}"
            signal_payload = {
                "label": signal_label,
                "direction": "call" if sig_type == "CALL" else "put",
                "line": line_name,
                "status": status,
                "signal_id": latest_signal.get("signal_id"),
                "explanation": latest_signal.get("explanation"),
                "rejection_time": latest_signal.get("rejection_time"),
                "rr_ratio": latest_signal.get("rr_ratio"),
            }

        # Guardrails — shape matches what the Next.js page expects:
        # list of { label, state, tone }
        decision = state.get("decision") or {}
        g = decision.get("guardrails") or {}
        guardrails_payload = _flatten_guardrails(g)

        # Top-level decision payload (action label + grade) — keeps the
        # page's Action and Grade cells out of placeholder text once a
        # signal exists.
        quality = state.get("signal_quality") or {}
        if decision or quality:
            final = decision.get("final_decision") if decision else None
            decision_payload = {
                "final_decision": final,
                "explanation": decision.get("explanation") if decision else None,
                "grade": quality.get("grade") if quality else None,
                "action_label": quality.get("action_label") if quality else None,
            }
            grade = quality.get("grade") if quality else None
            action = (
                quality.get("action_label")
                or _humanize(final)
                if (final or quality)
                else None
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
        bias=bias_payload,
        signal=signal_payload,
        guardrails=guardrails_payload,
        decision=decision_payload,
        grade=grade,
        action=action,
        intel=intel_cards,
    )


def _fetch_intel_for_live(spot_price: float | None) -> dict | None:
    """Inline UW intel fetch so /api/live can include intel cards in
    its response. Same source as /api/intel/spy but with a tiny shim
    so the live route doesn't import the route module."""
    from datetime import date

    from api.routes.intel import _gather_intel  # noqa: WPS437 — internal helper

    return _gather_intel(spot_price, date.today().isoformat())


def _build_intel_cards(intel_payload: dict | None) -> list[dict] | None:
    """Translate the UW intel dict into the page's
    [{label, value, body, tone}] intel-grid shape. Picks the four
    most decision-relevant facts: GEX dealer-side, Dark-pool dollar
    flow near spot, Recent flow tone, Market tide tone."""
    if not intel_payload or not intel_payload.get("available"):
        return None
    data = intel_payload.get("data") or {}
    cards: list[dict] = []

    gex = data.get("gex") or {}
    if isinstance(gex, dict) and gex.get("levels"):
        cards.append(
            {
                "label": "Dealer GEX",
                "value": gex.get("label") or "Mixed",
                "body": gex.get("summary") or "Strike-by-strike gamma exposure.",
                "tone": _gex_tone(gex),
            }
        )

    darkpool = data.get("darkpool")
    if isinstance(darkpool, dict):
        size_str = darkpool.get("dollar_size_label") or darkpool.get("dollar_size_str")
        nearest = darkpool.get("nearest_to_spot") or darkpool.get("nearest")
        cards.append(
            {
                "label": "Dark Pool",
                "value": size_str or "Active",
                "body": darkpool.get("summary")
                or (
                    f"Nearest print near {nearest}"
                    if nearest
                    else "Recent dark-pool prints in tape."
                ),
                "tone": "blue",
            }
        )

    recent = data.get("recent_flow")
    if isinstance(recent, dict):
        cards.append(
            {
                "label": "Recent flow",
                "value": recent.get("tone_label") or recent.get("dominant_side") or "Mixed",
                "body": recent.get("summary") or "Recent OTM SPY trade tape.",
                "tone": _flow_tone(recent),
            }
        )

    tide = data.get("market_tide")
    if isinstance(tide, dict):
        cards.append(
            {
                "label": "Market tide",
                "value": tide.get("tone") or tide.get("label") or "Neutral",
                "body": tide.get("summary") or "OTM-only market-wide tide.",
                "tone": _tide_tone(tide),
            }
        )

    return cards or None


def _gex_tone(gex: dict) -> str:
    label = (gex.get("label") or "").lower()
    if "negative" in label or "short gamma" in label:
        return "amber"
    if "positive" in label or "long gamma" in label:
        return "green"
    return "blue"


def _flow_tone(flow: dict) -> str:
    label = (flow.get("tone_label") or flow.get("dominant_side") or "").lower()
    if "bullish" in label or "call" in label:
        return "green"
    if "bearish" in label or "put" in label:
        return "amber"
    return "blue"


def _tide_tone(tide: dict) -> str:
    tone = (tide.get("tone") or "").lower()
    if "bullish" in tone or "supportive" in tone:
        return "green"
    if "bearish" in tone or "warning" in tone or "negative" in tone:
        return "amber"
    return "blue"


def _select_active_setup(
    desc_above: dict | None, desc_below: dict | None
) -> tuple[dict, str] | None:
    """Closer descending line wins; side determines setup direction."""
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


def _flatten_guardrails(g: dict) -> list[dict]:
    """Translate the DecisionState guardrail dict into the page's
    ``[{label, state, tone}]`` row shape. Tone reflects severity:
    green = clean, amber = caution, red = blocked."""
    if not g:
        return []
    rows: list[dict] = []

    chase = g.get("chase_status") or "—"
    chase_tone = "green"
    if chase == "MISSED_ENTRY":
        chase_tone = "red"
    elif chase == "NO_SIGNAL":
        chase_tone = "amber"
    rows.append(
        {
            "label": "Chase distance",
            "state": _humanize(chase),
            "tone": chase_tone,
        }
    )

    structure = g.get("structure_status") or "—"
    struct_tone = "green" if structure == "INTACT" else "red" if structure == "BROKEN" else "amber"
    rows.append(
        {
            "label": "Structure",
            "state": _humanize(structure),
            "tone": struct_tone,
        }
    )

    daily = g.get("daily_action") or "—"
    daily_tone = "green"
    if daily in {"STOP_TRADING", "NO_TRADE"}:
        daily_tone = "red"
    elif daily in {"SELECTIVE_TRADE", "WAIT"}:
        daily_tone = "amber"
    rows.append(
        {
            "label": "Daily risk",
            "state": _humanize(daily),
            "tone": daily_tone,
        }
    )

    return rows


def _humanize(s: str) -> str:
    return (s or "").replace("_", " ").title()


def _decision_label(spot_price: float | None) -> str:
    if spot_price is None:
        return "Awaiting market data"
    return "Live read · update on each close"
