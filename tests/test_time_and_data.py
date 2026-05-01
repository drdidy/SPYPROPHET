from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from app import (
    ensure_central_index,
    filter_extended_session,
    filter_rth_session,
    get_central_tz,
    get_latest_available_trading_day,
    get_live_signal_day,
    get_prior_trading_day,
)


def _sample_day_frame(day: str = "2026-04-28") -> pd.DataFrame:
    idx = pd.date_range(f"{day} 02:00", f"{day} 20:00", freq="1min", tz=get_central_tz())
    return pd.DataFrame({"Close": range(len(idx))}, index=idx)


def test_timezone_conversion_to_central_from_aware_utc() -> None:
    utc_idx = pd.date_range("2026-04-28 13:00", periods=2, freq="60min", tz="UTC")
    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=utc_idx)

    out = ensure_central_index(df)

    assert out.index.tz is not None
    assert str(out.index.tz) in {"US/Central", "America/Chicago"}
    assert out.index[0].hour == 8


def test_timezone_conversion_to_central_from_naive_assumed_utc() -> None:
    naive_idx = pd.date_range("2026-04-28 13:00", periods=1, freq="60min")
    df = pd.DataFrame({"Close": [1.0]}, index=naive_idx)

    out = ensure_central_index(df)

    assert out.index.tz is not None
    assert out.index[0].hour == 8


def test_rth_filter_boundaries() -> None:
    df = _sample_day_frame()
    day = date(2026, 4, 28)

    rth = filter_rth_session(df, day)

    assert not rth.empty
    assert datetime(2026, 4, 28, 8, 30, tzinfo=get_central_tz()) in rth.index
    assert datetime(2026, 4, 28, 15, 0, tzinfo=get_central_tz()) in rth.index
    assert datetime(2026, 4, 28, 8, 29, tzinfo=get_central_tz()) not in rth.index
    assert datetime(2026, 4, 28, 15, 1, tzinfo=get_central_tz()) not in rth.index


def test_rth_filter_excludes_after_close_hourly_bar() -> None:
    idx = pd.DatetimeIndex([
        datetime(2026, 4, 28, 8, 30, tzinfo=get_central_tz()),
        datetime(2026, 4, 28, 9, 30, tzinfo=get_central_tz()),
        datetime(2026, 4, 28, 14, 30, tzinfo=get_central_tz()),
        datetime(2026, 4, 28, 15, 0, tzinfo=get_central_tz()),
    ])
    df = pd.DataFrame({"Close": [1.0, 2.0, 3.0, 4.0]}, index=idx)

    rth = filter_rth_session(df, date(2026, 4, 28))

    assert datetime(2026, 4, 28, 14, 30, tzinfo=get_central_tz()) in rth.index
    assert datetime(2026, 4, 28, 15, 0, tzinfo=get_central_tz()) not in rth.index


def test_extended_filter_boundaries() -> None:
    df = _sample_day_frame()
    day = date(2026, 4, 28)

    ext = filter_extended_session(df, day)

    assert not ext.empty
    assert datetime(2026, 4, 28, 3, 0, tzinfo=get_central_tz()) in ext.index
    assert datetime(2026, 4, 28, 19, 0, tzinfo=get_central_tz()) in ext.index
    assert datetime(2026, 4, 28, 2, 59, tzinfo=get_central_tz()) not in ext.index
    assert datetime(2026, 4, 28, 19, 1, tzinfo=get_central_tz()) not in ext.index


def test_prior_trading_day_skips_missing_days() -> None:
    idx = pd.DatetimeIndex([
        datetime(2026, 4, 25, 9, 30, tzinfo=get_central_tz()),
        datetime(2026, 4, 29, 9, 30, tzinfo=get_central_tz()),
    ])
    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=idx)

    cur = datetime(2026, 4, 30, 10, 0, tzinfo=get_central_tz())
    prior = get_prior_trading_day(df, cur)

    assert prior == date(2026, 4, 29)


def test_live_signal_day_uses_current_day_before_first_loaded_candle() -> None:
    idx = pd.DatetimeIndex([
        datetime(2026, 4, 29, 9, 30, tzinfo=get_central_tz()),
        datetime(2026, 4, 30, 9, 30, tzinfo=get_central_tz()),
    ])
    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=idx)

    cur = datetime(2026, 5, 1, 7, 0, tzinfo=get_central_tz())

    assert get_latest_available_trading_day(df, cur) == date(2026, 4, 30)
    assert get_live_signal_day(df, cur) == date(2026, 5, 1)
    assert get_prior_trading_day(df, datetime(2026, 5, 1, tzinfo=get_central_tz())) == date(2026, 4, 30)


def test_empty_dataframe_handling() -> None:
    empty_df = pd.DataFrame()

    assert ensure_central_index(empty_df).empty
    assert filter_rth_session(empty_df, date(2026, 4, 28)).empty
    assert filter_extended_session(empty_df, date(2026, 4, 28)).empty
    assert get_prior_trading_day(empty_df, datetime(2026, 4, 30, tzinfo=get_central_tz())) is None
