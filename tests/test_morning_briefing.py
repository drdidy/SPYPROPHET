from __future__ import annotations

import pandas as pd

from app import (
    EconomicEvent,
    GammaExposureInsight,
    MarketMove,
    MorningBriefingBundle,
    OptionsIntelligence,
    SentimentContext,
    SourceStatus,
    StructureLearningProfile,
    TechnicalContext,
    build_openai_request_payload,
    build_morning_briefing_prompt,
    calculate_max_pain,
    filter_near_spy_strikes,
    rule_based_morning_briefing,
)


def test_calculate_max_pain_uses_open_interest() -> None:
    calls = pd.DataFrame({"strike": [100, 101, 102], "openInterest": [10, 100, 10]})
    puts = pd.DataFrame({"strike": [100, 101, 102], "openInterest": [10, 100, 10]})

    assert calculate_max_pain(calls, puts) == 101.0


def test_filter_near_spy_strikes_removes_far_open_interest() -> None:
    calls = pd.DataFrame({"strike": [500, 720, 725], "openInterest": [99999, 100, 200]})
    puts = pd.DataFrame({"strike": [510, 718, 716], "openInterest": [99999, 300, 200]})

    near_calls, near_puts = filter_near_spy_strikes(calls, puts, 721.0, width=10.0)

    assert 500 not in set(near_calls["strike"])
    assert 510 not in set(near_puts["strike"])


def _bundle() -> MorningBriefingBundle:
    now = pd.Timestamp("2026-05-01 06:30", tz="America/Chicago")
    options = OptionsIntelligence(
        SourceStatus("Options intelligence", "connected", "Delayed yfinance OI/volume proxy."),
        1.2,
        0.9,
        588.0,
        590.0,
        585.0,
        [{"type": "CALL", "strike": 590.0, "open_interest": 1000}],
    )
    gamma = GammaExposureInsight(
        SourceStatus("Gamma exposure", "unavailable", "GEX_API_URL is not configured; using OI magnet proxy."),
        None,
        "Proxy only",
        [585.0, 588.0, 590.0],
        "True dealer GEX is not available without GEX_API_URL.",
    )
    technical = TechnicalContext(
        SourceStatus("Yahoo Finance daily SPY", "connected", "Daily SPY history loaded."),
        589.0,
        584.0,
        587.0,
        580.0,
        550.0,
        590.0,
        582.0,
        595.0,
        570.0,
        1.1,
    )
    learning = StructureLearningProfile(20, 12, "CALL watch", "Moderate confidence", 0.58, 0.08, 0.25, 1.2, 2.3, -0.8, None, "Historical tendency only.")
    return MorningBriefingBundle(
        now,
        [{"code": "UD", "name": "Upper Call Trigger", "role": "Call Trigger", "value": 587.42, "anchor_price": 589.0, "anchor_time": "2026-04-30 15:00 CDT"}],
        [EconomicEvent(now.date(), "8:30 AM ET / 7:30 AM CT", "CPI", "High", "Local calendar", "Inflation release")],
        [MarketMove("ES futures", "ES=F", 5900.0, 20.0, 0.34, now, "Yahoo Finance")],
        [],
        [MarketMove("Technology", "XLK", 240.0, 1.5, 0.63, now, "Yahoo Finance")],
        options,
        gamma,
        SentimentContext(SourceStatus("Headline sentiment", "connected", "Headline score."), 2, "Bullish headlines", 3, 1),
        technical,
        [],
        learning,
        [options.status, gamma.status, technical.status],
    )


def test_prompt_carries_truthful_source_statuses() -> None:
    prompt = build_morning_briefing_prompt(_bundle())

    assert "Do not invent unavailable options flow" in prompt
    assert "SCOUT_LIST_JSON" in prompt
    assert "Tradytics" in prompt
    assert "GEX_API_URL is not configured" in prompt
    assert "CPI" in prompt
    assert "Upper Call Trigger" in prompt


def test_rule_based_briefing_marks_unavailable_premium_feeds() -> None:
    result = rule_based_morning_briefing(_bundle(), ai_warning="OPENAI_API_KEY is not configured.")

    assert result.provider == "Rule-based verified briefing"
    assert any("OPENAI_API_KEY is not configured" in warning for warning in result.warnings)
    assert "True dealer GEX is not available" not in result.text
    assert any("GEX_API_URL is not configured" in warning for warning in result.warnings)
    assert "CPI at 8:30 AM ET / 7:30 AM CT" in result.text


def test_openai_request_payload_enables_web_search() -> None:
    payload = build_openai_request_payload("brief me", "gpt-4.1-mini", enable_web_search=True)

    assert payload["tools"][0]["type"] == "web_search"
    assert payload["tools"][0]["user_location"]["timezone"] == "America/Chicago"
    assert payload["include"] == ["web_search_call.action.sources"]
