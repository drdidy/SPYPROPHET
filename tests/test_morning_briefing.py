from __future__ import annotations

import pandas as pd

from app import (
    EconomicEvent,
    GammaExposureInsight,
    MarketMove,
    MorningBriefingBundle,
    MorningBriefingResult,
    OptionsIntelligence,
    SentimentContext,
    SourceStatus,
    StructureLearningProfile,
    TechnicalContext,
    build_openai_calendar_prompt,
    build_openai_request_payload,
    build_morning_briefing_prompt,
    economic_event_from_ai_calendar_dict,
    extract_json_payload_from_text,
    fallback_morning_decision,
    merge_citations,
    morning_decision_from_result,
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
    assert "Return ONLY valid JSON" in prompt
    assert '"primary_trade"' in prompt
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


def test_calendar_prompt_requires_verified_json_rows() -> None:
    prompt = build_openai_calendar_prompt(pd.Timestamp("2026-05-01 06:30", tz="America/Chicago"))

    assert "Return ONLY a JSON object" in prompt
    assert "Investing.com Economic Calendar" in prompt
    assert "ForexFactory Calendar" in prompt
    assert "2026-05-01" in prompt
    assert '"events"' in prompt


def test_extract_json_payload_from_text_handles_markdown_fences() -> None:
    text = '```json\n{"events":[{"event":"NFP","impact":"High"}]}\n```'

    assert extract_json_payload_from_text(text) == {"events": [{"event": "NFP", "impact": "High"}]}


def test_morning_decision_parser_reads_structured_ai_output() -> None:
    result = MorningBriefingResult(
        pd.Timestamp("2026-05-01 06:45", tz="America/Chicago"),
        "OpenAI",
        "gpt-5.2",
        '{"stance":"WATCH_PUT","headline":"Wait for Upper Put Trigger rejection.","primary_trade":{"trigger_line":"Upper Put Trigger","trigger_price":"722.42","contract":"PUT 718","confidence":61},"why":["ISM at 9:00 AM CT"],"avoid":[{"label":"Chase","reason":"Between lines"}],"risk_flags":["0DTE spread risk"],"source_notes":[],"novice_summary":"Wait for confirmation."}',
        61,
        [],
        [],
        [],
    )

    decision = morning_decision_from_result(result)

    assert decision is not None
    assert decision["stance"] == "WATCH_PUT"
    assert decision["primary_trade"]["contract"] == "PUT 718"
    assert decision["avoid"][0]["label"] == "Chase"


def test_merge_citations_dedupes_normalized_urls() -> None:
    citations = merge_citations(
        [{"url": "https://example.com/a/", "title": "A"}, {"url": "https://example.com/a#section", "title": "A again"}],
        [{"url": "https://example.com/b", "title": "B"}],
    )

    assert [row["url"] for row in citations] == ["https://example.com/a", "https://example.com/b"]


def test_fallback_decision_matches_contract_to_trigger_side() -> None:
    bundle = _bundle()
    bundle = MorningBriefingBundle(
        bundle.generated_at,
        [{"code": "UA", "name": "Upper Put Trigger", "role": "Put Trigger", "value": 722.42, "anchor_price": 719.79, "anchor_time": "2026-04-30 15:00 CDT"}],
        bundle.economic_events,
        bundle.global_context,
        bundle.macro_context,
        bundle.sector_context,
        OptionsIntelligence(
            bundle.options_intelligence.status,
            bundle.options_intelligence.put_call_open_interest_ratio,
            bundle.options_intelligence.put_call_volume_ratio,
            bundle.options_intelligence.max_pain,
            bundle.options_intelligence.call_wall,
            bundle.options_intelligence.put_wall,
            [],
            [{"type": "CALL", "strike": 724.0}, {"type": "PUT", "strike": 720.0}],
        ),
        bundle.gamma_insight,
        bundle.sentiment,
        bundle.technical_context,
        bundle.news_items,
        bundle.learning_profile,
        bundle.source_statuses,
    )

    decision = fallback_morning_decision(bundle)

    assert decision["primary_trade"]["contract"] == "PUT 720"


def test_ai_calendar_event_requires_exact_date_time_and_source() -> None:
    event = economic_event_from_ai_calendar_dict(
        {
            "event_date": "2026-05-01",
            "time_label": "8:30 AM ET / 7:30 AM CT",
            "event": "ISM Manufacturing PMI",
            "impact": "High",
            "source": "Investing.com",
            "notes": "Forecast 49.0; previous 49.0",
        }
    )

    assert event is not None
    assert event.event_date == pd.Timestamp("2026-05-01").date()
    assert event.time_label == "8:30 AM ET / 7:30 AM CT"
    assert event.source == "Investing.com"
    assert event.impact == "High"

    assert economic_event_from_ai_calendar_dict({"event": "CPI", "event_date": "2026-05-01"}) is None
