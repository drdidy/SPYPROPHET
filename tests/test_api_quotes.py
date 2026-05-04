from __future__ import annotations

from fastapi.testclient import TestClient

from api import deps
from api.main import create_app
from api.routes import quotes as quotes_route


def test_quotes_returns_503_when_secrets_missing(monkeypatch):
    for k in ("TASTYTRADE_CLIENT_ID", "TASTYTRADE_CLIENT_SECRET", "TASTYTRADE_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    deps.reset_provider_for_tests()
    deps.get_cache().clear()
    client = TestClient(create_app())
    r = client.get("/api/quotes/spy")
    assert r.status_code == 503
    body = r.json()
    assert body["detail"]["error"] == "tastytrade_unconfigured"
    assert "TASTYTRADE_CLIENT_ID" in body["detail"]["missing_secrets"]


def test_quotes_returns_pair_with_provider_stub(monkeypatch):
    monkeypatch.setenv("TASTYTRADE_CLIENT_ID", "id")
    monkeypatch.setenv("TASTYTRADE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TASTYTRADE_REFRESH_TOKEN", "refresh")
    deps.reset_provider_for_tests()
    deps.get_cache().clear()

    monkeypatch.setattr(
        quotes_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 623.0, "change": 1.2, "change_pct": 0.19},
    )

    fake_status = {
        "provider": "TASTYTRADE",
        "connected": True,
        "using_live_quotes": True,
        "environment": "production",
        "last_error": None,
        "last_update": None,
        "missing_secrets": [],
        "auth_ok": True,
        "chain_ok": True,
        "quotes_ok": True,
    }

    def fake_quotes(self, underlying_price, expiration, call_strike, put_strike):
        return {
            "CALL": {
                "symbol": f"SPY-{call_strike}-C",
                "underlying": "SPY",
                "expiration": expiration,
                "strike": call_strike,
                "option_type": "CALL",
                "bid": 1.10,
                "ask": 1.30,
                "mark": 1.20,
                "spread": 0.20,
                "delta": 0.42,
                "gamma": 0.10,
                "theta": -0.30,
                "vega": 0.02,
                "iv": 0.23,
                "provider": "TASTYTRADE_LIVE",
                "warning": None,
            },
            "PUT": {
                "symbol": f"SPY-{put_strike}-P",
                "underlying": "SPY",
                "expiration": expiration,
                "strike": put_strike,
                "option_type": "PUT",
                "bid": 1.00,
                "ask": 1.20,
                "mark": 1.10,
                "spread": 0.20,
                "delta": -0.39,
                "gamma": 0.10,
                "theta": -0.31,
                "vega": 0.02,
                "iv": 0.24,
                "provider": "TASTYTRADE_LIVE",
                "warning": None,
            },
            "status": fake_status,
            "warning": None,
        }

    from tastytrade_provider import TastytradeProvider

    monkeypatch.setattr(TastytradeProvider, "get_selected_quotes", fake_quotes)

    client = TestClient(create_app())
    r = client.get("/api/quotes/spy?expiration=2026-05-04")
    assert r.status_code == 200
    body = r.json()
    assert body["underlying"] == "SPY"
    assert body["expiration"] == "2026-05-04"
    assert body["underlying_price"] == 623.0
    # spot 623.0 → call ≈ 625, put ≈ 621
    assert body["call"]["strike"] == 625
    assert body["put"]["strike"] == 621
    assert body["call"]["provider"] == "TASTYTRADE_LIVE"
    assert body["call"]["delta"] == 0.42
    assert body["put"]["delta"] == -0.39
    assert body["provider_status"]["quotes_ok"] is True
