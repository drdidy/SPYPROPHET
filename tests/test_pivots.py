from __future__ import annotations

from datetime import datetime

import pandas as pd

from app import (
    candle_color,
    find_high_pivot,
    find_low_pivot,
    find_secondary_pivots,
    get_central_tz,
)


def _df(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([datetime.fromisoformat(ts).replace(tzinfo=get_central_tz()) for ts, *_ in rows])
    data = {
        "Open": [r[1] for r in rows],
        "High": [r[2] for r in rows],
        "Low": [r[3] for r in rows],
        "Close": [r[4] for r in rows],
    }
    return pd.DataFrame(data, index=idx)


def test_candle_color() -> None:
    assert candle_color(pd.Series({"Open": 1, "Close": 2})) == "green"
    assert candle_color(pd.Series({"Open": 2, "Close": 1})) == "red"
    assert candle_color(pd.Series({"Open": 2, "Close": 2})) == "doji"


def test_high_pivot_found() -> None:
    df = _df([
        ("2026-04-28T08:30:00", 10, 11, 9, 11),
        ("2026-04-28T09:30:00", 11, 12, 10, 10),
    ])
    p = find_high_pivot(df)
    assert p.price == 12
    assert p.timestamp == df.index[1]
    assert p.fallback_used is False
    assert p.source == "session_high"


def test_low_pivot_found() -> None:
    df = _df([
        ("2026-04-28T08:30:00", 10, 11, 8, 9),
        ("2026-04-28T09:30:00", 9, 10, 8.5, 10),
    ])
    p = find_low_pivot(df)
    assert p.price == 8
    assert p.timestamp == df.index[0]
    assert not p.fallback_used
    assert p.candle_color == "red"


def test_newest_pattern_selected_for_high_and_low() -> None:
    df = _df([
        ("2026-04-28T08:30:00", 10, 12, 9, 11),
        ("2026-04-28T09:30:00", 11, 11.5, 10, 10),
        ("2026-04-28T10:30:00", 10, 11, 8, 9),
        ("2026-04-28T11:30:00", 9, 10, 8.5, 10),
        ("2026-04-28T12:30:00", 10, 13, 9.5, 12),
        ("2026-04-28T13:30:00", 12, 12.1, 11, 11),
        ("2026-04-28T14:30:00", 11, 11.2, 7, 8),
        ("2026-04-28T15:00:00", 8, 9, 7.5, 9),
    ])
    hp = find_high_pivot(df)
    lp = find_low_pivot(df)
    assert hp.timestamp == df.index[4]
    assert lp.timestamp == df.index[6]


def test_doji_does_not_invalidate_session_extreme_primary() -> None:
    df = _df([
        ("2026-04-28T08:30:00", 10, 12, 9, 11),
        ("2026-04-28T09:30:00", 11, 12, 10, 11),
        ("2026-04-28T10:30:00", 11, 12, 10, 10),
    ])
    hp = find_high_pivot(df)
    assert hp.price == 12 and not hp.fallback_used and hp.source == "session_high"

    df2 = _df([
        ("2026-04-28T08:30:00", 10, 11, 8, 9),
        ("2026-04-28T09:30:00", 9, 10, 8.5, 9),
        ("2026-04-28T10:30:00", 9, 10, 8.5, 10),
    ])
    lp = find_low_pivot(df2)
    assert lp.price == 8 and not lp.fallback_used and lp.source == "session_low"


def test_fallbacks() -> None:
    high_no_pattern = _df([
        ("2026-04-28T08:30:00", 10, 11, 9, 11),
        ("2026-04-28T09:30:00", 11, 15, 10, 12),
        ("2026-04-28T10:30:00", 12, 13, 11, 13),
    ])
    hp = find_high_pivot(high_no_pattern)
    assert not hp.fallback_used and hp.price == 15 and hp.timestamp == high_no_pattern.index[1]

    low_no_pattern = _df([
        ("2026-04-28T08:30:00", 10, 11, 8, 9),
        ("2026-04-28T09:30:00", 9, 10, 6, 8),
        ("2026-04-28T10:30:00", 8, 9, 7, 7),
    ])
    lp = find_low_pivot(low_no_pattern)
    assert not lp.fallback_used and lp.price == 6 and lp.timestamp == low_no_pattern.index[1]


def test_secondary_pivots() -> None:
    df = _df([
        ("2026-04-28T08:30:00", 10, 10.5, 9, 9),   # red
        ("2026-04-28T09:30:00", 9, 10.6, 8.8, 10), # green => descending from first
        ("2026-04-28T10:30:00", 10, 11.0, 9.7, 9), # red => ascending from second
        ("2026-04-28T11:30:00", 9, 9.8, 8.2, 9),   # doji
        ("2026-04-28T12:30:00", 9, 9.5, 7.5, 8),   # red
        ("2026-04-28T13:30:00", 8, 9.2, 7.2, 9),   # green => descending from fifth
    ])
    pivots = find_secondary_pivots(df)
    assert len(pivots) == 3
    assert pivots[0].direction == "descending" and pivots[0].price == 9
    assert pivots[1].direction == "ascending" and pivots[1].price == 10.6
    assert pivots[2].direction == "descending" and pivots[2].price == 7.5
    assert [p.timestamp for p in pivots] == sorted([p.timestamp for p in pivots])


def test_empty_rth_handling() -> None:
    empty = pd.DataFrame()
    hp = find_high_pivot(empty)
    lp = find_low_pivot(empty)
    sp = find_secondary_pivots(empty)
    assert hp.timestamp is None and hp.fallback_used
    assert lp.timestamp is None and lp.fallback_used
    assert sp == []
