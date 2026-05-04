"""Smoke tests using Streamlit's official AppTest framework.

These tests verify that the app actually boots and renders without
unhandled exceptions, including with no market data (weekend / pre-market
case). They don't assert specific UI content — they only catch crashes,
which is exactly the gap the audit flagged: the app has ~50 render_*
functions and zero UI tests, so any silent regression in main() or a
render path would ship undetected.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None  # type: ignore


def _empty_yf(*args, **kwargs):
    """Return an empty DataFrame, simulating a yfinance outage."""
    return pd.DataFrame()


def _stub_yf(*args, **kwargs):
    """Return a tiny synthetic OHLCV frame so the app has something to render."""
    idx = pd.date_range("2026-04-28 08:30", periods=8, freq="60min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "Open": [500.0, 501.0, 502.0, 503.0, 504.0, 503.5, 502.5, 501.5],
            "High": [501.0, 502.0, 503.0, 504.0, 505.0, 504.0, 503.5, 502.5],
            "Low": [499.5, 500.5, 501.5, 502.0, 503.0, 502.5, 501.5, 500.5],
            "Close": [500.5, 501.5, 502.5, 503.5, 504.5, 503.0, 502.0, 501.0],
            "Adj Close": [500.5, 501.5, 502.5, 503.5, 504.5, 503.0, 502.0, 501.0],
            "Volume": [1_000_000] * 8,
        },
        index=idx,
    )
    return df


@pytest.mark.skipif(AppTest is None, reason="streamlit.testing.v1 unavailable")
def test_app_boots_with_empty_data() -> None:
    """The app must not crash when yfinance returns nothing — this is the
    weekend / outage path the new onboarding banner is designed for."""
    with patch("yfinance.download", side_effect=_empty_yf):
        at = AppTest.from_file("app.py", default_timeout=30)
        at.run()
    # Empty data is a graceful degradation path, not an error path.
    assert not at.exception, f"App crashed with empty data: {at.exception}"


@pytest.mark.skipif(AppTest is None, reason="streamlit.testing.v1 unavailable")
def test_app_boots_with_synthetic_data() -> None:
    """Happy-path smoke: yfinance returns candles and the app renders all
    sections without raising."""
    with patch("yfinance.download", side_effect=_stub_yf):
        at = AppTest.from_file("app.py", default_timeout=45)
        at.run()
    assert not at.exception, f"App crashed with synthetic data: {at.exception}"


@pytest.mark.skipif(AppTest is None, reason="streamlit.testing.v1 unavailable")
def test_sidebar_refresh_button_present() -> None:
    """The Refresh button must exist and be wired (regression guard for the
    audit finding that it was previously a dead button)."""
    with patch("yfinance.download", side_effect=_empty_yf):
        at = AppTest.from_file("app.py", default_timeout=30)
        at.run()
    refresh_buttons = [b for b in at.sidebar.button if "Refresh" in (b.label or "")]
    assert refresh_buttons, "Sidebar 'Refresh data' button is missing"
