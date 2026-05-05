from __future__ import annotations

from fastapi.testclient import TestClient

from api import deps
from api.main import create_app
from api.routes import options as options_route


def test_options_503_when_secrets_missing(monkeypatch):
    for k in ("TASTYTRADE_CLIENT_ID", "TASTYTRADE_CLIENT_SECRET", "TASTYTRADE_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    deps.reset_provider_for_tests()
    deps.get_cache().clear()
    client = TestClient(create_app())
    r = client.get("/api/options/spy")
    assert r.status_code == 503


def test_options_returns_strikes_around_spot(monkeypatch):
    monkeypatch.setenv("TASTYTRADE_CLIENT_ID", "id")
    monkeypatch.setenv("TASTYTRADE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TASTYTRADE_REFRESH_TOKEN", "refresh")
    deps.reset_provider_for_tests()
    deps.get_cache().clear()

    monkeypatch.setattr(
        options_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 718.0, "change": 1.2, "change_pct": 0.17},
    )

    chain_payload = {
        "data": {
            "items": [
                {
                    "underlying-symbol": "SPY",
                    "expirations": [
                        {
                            "expiration-date": "2026-05-05",
                            "strikes": [
                                {
                                    "strike-price": str(strike),
                                    "call": f"SPY-C-{strike}",
                                    "put": f"SPY-P-{strike}",
                                    "call-streamer-symbol": f".SPY260505C{strike}",
                                    "put-streamer-symbol": f".SPY260505P{strike}",
                                }
                                for strike in range(700, 740)
                            ],
                        }
                    ],
                }
            ]
        }
    }

    from tastytrade_provider import TastytradeProvider

    monkeypatch.setattr(
        TastytradeProvider,
        "get_nested_option_chain",
        lambda self, symbol, expiration: chain_payload,
    )

    client = TestClient(create_app())
    r = client.get("/api/options/spy?expiration=2026-05-05&width=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["underlying"] == "SPY"
    assert body["expiration"] == "2026-05-05"
    assert body["spot_price"] == 718.0
    # width=5 → 10 strikes total, sorted ascending
    assert len(body["strikes"]) == 10
    strikes_only = [s["strike"] for s in body["strikes"]]
    assert strikes_only == sorted(strikes_only)
    # Should include the strike at spot
    assert 718.0 in strikes_only
    assert all("call_symbol" in s and "put_symbol" in s for s in body["strikes"])
    # Streamer symbols round-trip
    assert body["strikes"][0]["call_streamer_symbol"].startswith(".SPY260505C")


def test_options_404_for_unknown_expiration(monkeypatch):
    monkeypatch.setenv("TASTYTRADE_CLIENT_ID", "id")
    monkeypatch.setenv("TASTYTRADE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TASTYTRADE_REFRESH_TOKEN", "refresh")
    deps.reset_provider_for_tests()
    deps.get_cache().clear()

    monkeypatch.setattr(
        options_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 718.0, "change": 0.0, "change_pct": 0.0},
    )

    from tastytrade_provider import TastytradeProvider

    monkeypatch.setattr(
        TastytradeProvider,
        "get_nested_option_chain",
        lambda self, symbol, expiration: {"data": {"items": []}},
    )

    client = TestClient(create_app())
    r = client.get("/api/options/spy?expiration=2099-01-01")
    assert r.status_code == 404
