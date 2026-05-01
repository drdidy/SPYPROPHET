from __future__ import annotations

from datetime import datetime

import pandas as pd

from app import (
    DynamicLine,
    build_market_context,
    calculate_spy_pressure,
    classify_vix,
    get_central_tz,
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
