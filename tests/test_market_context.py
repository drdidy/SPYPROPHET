from __future__ import annotations

from datetime import datetime

import pandas as pd

from app import (
    DynamicLine,
    JournalEntry,
    build_structure_learning_profile,
    build_market_context,
    calculate_spy_pressure,
    classify_vix,
    classify_news_relevance,
    get_central_tz,
    get_upcoming_economic_events,
    is_market_news_relevant,
    load_economic_calendar,
    make_journal_id,
    economic_event_from_trading_economics,
    parse_rss_items,
)


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(datetime.fromisoformat(s), tz=get_central_tz())


def test_vix_regime_labels() -> None:
    assert classify_vix(14.9)[0] == "Calm"
    assert classify_vix(18.0)[0] == "Normal"
    assert classify_vix(22.0)[0] == "Elevated"
    assert classify_vix(28.0)[0] == "Stress"
    assert classify_vix(float("nan"))[0] == "Unavailable"


def test_spy_pressure_uses_recent_hourly_closes() -> None:
    idx = pd.date_range("2026-04-30 08:30", periods=5, freq="60min", tz=get_central_tz())
    rising = pd.DataFrame({"Close": [100.0, 100.5, 101.0, 102.0, 103.2]}, index=idx)
    fading = pd.DataFrame({"Close": [103.2, 102.0, 101.0, 100.5, 99.0]}, index=idx)
    flat = pd.DataFrame({"Close": [100.0, 100.2, 100.1, 100.3, 100.4]}, index=idx)

    assert calculate_spy_pressure(rising)[0] == "Lifting"
    assert calculate_spy_pressure(fading)[0] == "Fading"
    assert calculate_spy_pressure(flat)[0] == "Balanced"


def test_market_context_trigger_gap() -> None:
    idx = pd.date_range("2026-04-30 08:30", periods=5, freq="60min", tz=get_central_tz())
    df = pd.DataFrame({"Close": [100.0, 100.5, 101.0, 101.5, 102.0]}, index=idx)
    line = DynamicLine("UD", 101.8, _ts("2026-04-30T08:30:00"), 0.0, "descending", "CALL_ZONE", "PRIMARY_HIGH", True, "")

    ctx = build_market_context(df, 102.0, line, idx[-1], vix_price=18.0)

    assert ctx.vix_label == "Normal"
    assert ctx.spy_pressure == "Lifting"
    assert ctx.trigger_gap_label == "At trigger"
    assert abs(ctx.trigger_gap - 0.2) < 1e-9


def test_parse_rss_items_and_relevance() -> None:
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Fed and CPI data move SPY before the open</title>
        <link>https://example.com/story</link>
        <description><![CDATA[<p>Yields and volatility rose.</p>]]></description>
        <pubDate>Fri, 01 May 2026 13:30:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    items = parse_rss_items(xml, source="Test", limit=3)

    assert len(items) == 1
    assert items[0].source == "Test"
    assert items[0].summary == "Yields and volatility rose."
    assert items[0].relevance == "Macro catalyst"
    assert classify_news_relevance("VIX jumps as Treasury yields rise") == "Volatility watch"
    assert is_market_news_relevant("VIX jumps as Treasury yields rise")
    assert not is_market_news_relevant("Why paying off your mortgage could cost more than investing")


def test_economic_calendar_loads_and_filters(tmp_path) -> None:
    path = tmp_path / "calendar.json"
    path.write_text(
        """
        {"events": [
          {"date": "2026-05-01", "time": "8:30 AM ET", "event": "Jobs report", "impact": "High"},
          {"date": "2026-05-12", "time": "8:30 AM ET", "event": "CPI", "impact": "High"}
        ]}
        """
    )

    events = load_economic_calendar(str(path))
    upcoming = get_upcoming_economic_events(_ts("2026-05-01T07:00:00"), days=3, path=str(path))

    assert len(events) == 2
    assert len(upcoming) == 1
    assert upcoming[0].event == "Jobs report"


def test_trading_economics_event_mapping() -> None:
    event = economic_event_from_trading_economics({
        "Date": "2026-05-01T12:30:00",
        "Event": "Non Farm Payrolls",
        "Importance": 3,
        "Source": "Bureau of Labor Statistics",
        "Forecast": "200K",
        "Previous": "180K",
    })

    assert event is not None
    assert event.event == "Non Farm Payrolls"
    assert event.impact == "High"
    assert "ET" in event.time_label
    assert "Forecast 200K" in event.notes


def _journal_entry(signal_id: str, signal_type: str, line_name: str, outcome: str) -> JournalEntry:
    e = JournalEntry(
        "",
        _ts("2026-04-29T10:00:00"),
        None,
        _ts("2026-04-29T10:00:00").date(),
        "TEST",
        signal_id,
        signal_type,
        "CONFIRMED",
        line_name,
        None,
        "NEUTRAL",
        "A",
        90.0,
        "TRADE_ALLOWED",
        "TRADE_ALLOWED",
        _ts("2026-04-29T09:00:00"),
        _ts("2026-04-29T10:00:00"),
        100.0,
        99.0,
        "TARGET",
        102.0,
        2.0,
        outcome,
        _ts("2026-04-29T12:00:00"),
        2.5,
        -0.4,
        2,
        signal_type,
        102,
        2.1,
        3.1,
        100.0,
        "TEST",
        None,
        [],
    )
    return e.__class__(make_journal_id(e), *list(e.__dict__.values())[1:])


def test_structure_learning_profile_prefers_matching_samples() -> None:
    entries = [
        _journal_entry("c1", "CALL", "UD", "TARGET_FIRST"),
        _journal_entry("c2", "CALL", "UD", "TARGET_FIRST"),
        _journal_entry("p1", "PUT", "UA", "STOP_FIRST"),
    ]
    signal = type("Signal", (), {"signal_type": "CALL", "line_name": "UD"})()

    profile = build_structure_learning_profile(entries, active_signal=signal)

    assert profile.sample_size == 3
    assert profile.matching_sample_size == 2
    assert profile.target_first_rate == 1.0
    assert profile.stop_first_rate == 0.0
