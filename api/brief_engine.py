"""Wrapper around app.py's morning briefing engine.

Builds a ``MorningBriefingBundle`` from the same inputs the Streamlit
app uses (primary lines from prior session pivots, economic events,
news, learning profile, etc.) and calls ``generate_morning_briefing``
with ``use_ai=True`` to get the OpenAI-synthesized structured decision.

Some sub-fetches (technical context, global tape) currently rely on
yfinance and may return empty data from cloud egress IPs — but the
briefing engine handles those gracefully and the OpenAI synthesis
still produces a structured result based on the available context.
"""
from __future__ import annotations

import logging
from datetime import timedelta as _td

logger = logging.getLogger("spyprophet.api.brief_engine")


def _resolve_pivot_session(df, now):
    from app import filter_rth_session

    candidate = now.date() - _td(days=1)
    while candidate.weekday() >= 5:
        candidate -= _td(days=1)
    for _ in range(7):
        rth = filter_rth_session(df, candidate)
        if rth is not None and not rth.empty:
            return candidate, rth
        candidate -= _td(days=1)
        while candidate.weekday() >= 5:
            candidate -= _td(days=1)
    return None, None


def generate_ai_brief(spot_price: float | None, now_dt=None) -> dict | None:
    import pandas as pd

    try:
        from app import (
            briefing_bundle_to_dict,
            build_morning_briefing_bundle,
            build_primary_lines,
            fetch_market_news,
            find_high_pivot,
            find_low_pivot,
            generate_morning_briefing,
            get_central_tz,
            get_structure_projection_time,
            get_upcoming_economic_events,
            morning_decision_from_result,
        )
    except Exception as exc:
        logger.warning("brief engine imports failed: %s", type(exc).__name__)
        return None

    from api.structure import fetch_spy_hourly_dataframe

    df = fetch_spy_hourly_dataframe(period="10d")
    if df.empty:
        logger.warning("brief engine: hourly dataframe empty")
        return None

    ct = get_central_tz()
    now = pd.Timestamp(now_dt) if now_dt is not None else pd.Timestamp.now(tz=ct)
    if now.tzinfo is None:
        now = now.tz_localize(ct)
    else:
        now = now.tz_convert(ct)

    pivot_day, pivot_rth = _resolve_pivot_session(df, now)
    if pivot_rth is None:
        logger.warning("brief engine: no pivot session available")
        return None

    high_pivot = find_high_pivot(pivot_rth)
    low_pivot = find_low_pivot(pivot_rth)
    primary_lines = build_primary_lines(high_pivot, low_pivot)
    projection_time = get_structure_projection_time(now, hour=9, minute=0)

    try:
        news_items = fetch_market_news(limit=8)
    except Exception as exc:
        logger.warning("brief news fetch failed: %s", type(exc).__name__)
        news_items = []

    try:
        events = get_upcoming_economic_events(now, days=7)
    except Exception as exc:
        logger.warning("brief events fetch failed: %s", type(exc).__name__)
        events = []

    try:
        from app import StructureLearningProfile

        learning_profile = StructureLearningProfile(
            sample_size=0,
            matching_sample_size=0,
            expected_direction="UNKNOWN",
            confidence_label="LIMITED",
            target_first_rate=0.0,
            stop_first_rate=0.0,
            no_hit_rate=0.0,
            average_rr=0.0,
            average_max_favorable_move=0.0,
            average_max_adverse_move=0.0,
            best_context=None,
            caveat="Learning profile not yet populated; journal-driven calibration coming.",
        )
    except Exception:
        learning_profile = None

    try:
        bundle = build_morning_briefing_bundle(
            primary_lines=primary_lines,
            projection_time=projection_time,
            economic_events=events,
            news_items=news_items,
            learning_profile=learning_profile,
            latest_price=spot_price,
            selected_strikes=None,
            option_state=None,
            hourly_df=df,
        )
    except Exception as exc:
        logger.warning("brief bundle build failed: %s", type(exc).__name__)
        return None

    try:
        result = generate_morning_briefing(bundle, use_ai=True)
    except Exception as exc:
        logger.warning("brief OpenAI call failed: %s", type(exc).__name__)
        return None

    decision = morning_decision_from_result(result)
    if decision is None:
        return None

    bundle_dict = briefing_bundle_to_dict(bundle)

    return {
        "generated_at": result.generated_at.isoformat() if hasattr(result.generated_at, "isoformat") else str(result.generated_at),
        "provider": result.provider,
        "model": result.model,
        "confidence": result.confidence,
        "decision": decision,
        "warnings": list(result.warnings or []),
        "citations": list(result.citations or []),
        "source_statuses": [_status_to_dict(s) for s in (bundle.source_statuses or [])],
        "external_context": _extract_external_context(bundle_dict),
    }


def _status_to_dict(s) -> dict:
    return {
        "name": getattr(s, "name", None),
        "status": getattr(s, "status", None),
        "detail": getattr(s, "detail", None),
        "as_of": (
            s.as_of.isoformat()
            if hasattr(s.as_of, "isoformat") and s.as_of is not None
            else None
        ),
        "url": getattr(s, "url", None),
    }


def _extract_external_context(bundle: dict) -> dict:
    options_intel = bundle.get("options_intel") or {}
    gamma = bundle.get("gamma") or {}
    global_context = bundle.get("global_context") or []
    sector_context = bundle.get("sector_context") or []
    sentiment = bundle.get("sentiment") or {}
    technical = bundle.get("technical") or {}

    uw = options_intel.get("unusual_whales") if isinstance(options_intel, dict) else None
    darkpool = None
    gex = None
    flow_alerts = None
    if isinstance(uw, dict):
        darkpool = uw.get("darkpool") if isinstance(uw.get("darkpool"), dict) else None
        flow_alerts = uw.get("flow_alerts") or uw.get("recent_flow") or None
        gex_section = uw.get("gex") if isinstance(uw.get("gex"), dict) else None
        if gex_section:
            gex = gex_section
    if gex is None and isinstance(gamma, dict):
        gex = {
            "label": gamma.get("label"),
            "summary": gamma.get("summary"),
            "walls": gamma.get("walls") or [],
        }

    return {
        "dark_pool": darkpool,
        "dealer_gex": gex,
        "flow_alerts": flow_alerts,
        "global_context": global_context,
        "sector_context": sector_context,
        "sentiment": sentiment,
        "technical": technical,
    }
