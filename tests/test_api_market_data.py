from __future__ import annotations

from api.market_data import classify_vix, watch_strikes


def test_watch_strikes_round_to_nearest_dollar():
    s = watch_strikes(623.4)
    assert s == {"call": 625, "put": 621}


def test_watch_strikes_handle_missing_spot():
    assert watch_strikes(None) == {"call": None, "put": None}


def test_watch_strikes_custom_distance():
    assert watch_strikes(500.0, distance=5.0) == {"call": 505, "put": 495}


def test_classify_vix_buckets():
    assert classify_vix(12)[0] == "Calm"
    assert classify_vix(17)[0] == "Moderate"
    assert classify_vix(22)[0] == "Elevated"
    assert classify_vix(27)[0] == "High"
    assert classify_vix(40)[0] == "Extreme"
    # Tones
    assert classify_vix(12)[1] == "green"
    assert classify_vix(22)[1] == "amber"
    assert classify_vix(40)[1] == "red"
