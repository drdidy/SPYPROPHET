from __future__ import annotations

from fastapi.testclient import TestClient

from api import deps
from api.main import create_app
from api.routes import live as live_route


def test_live_snapshot_uses_market_data_helpers(monkeypatch):
    deps.get_cache().clear()
    monkeypatch.setattr(
        live_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 623.41, "change": 6.41, "change_pct": 1.04},
    )
    monkeypatch.setattr(
        live_route,
        "fetch_vix_snapshot",
        lambda: {"value": 14.82, "regime": "Calm", "regime_tone": "green"},
    )

    client = TestClient(create_app())
    r = client.get("/api/live")
    assert r.status_code == 200
    body = r.json()

    assert body["spot"]["price"] == 623.41
    assert body["spot"]["change_pct"] == 1.04
    assert body["vix"]["value"] == 14.82
    assert body["vix"]["regime"] == "Calm"
    assert body["vix"]["regime_tone"] == "green"
    # spot 623.41 → call 625, put 621
    assert body["watch"]["call"] == 625
    assert body["watch"]["put"] == 621
    assert body["decision_label"]
    assert body["last_update"]


def test_live_snapshot_handles_missing_data(monkeypatch):
    deps.get_cache().clear()
    monkeypatch.setattr(
        live_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": None, "change": None, "change_pct": None},
    )
    monkeypatch.setattr(
        live_route,
        "fetch_vix_snapshot",
        lambda: {"value": None, "regime": None, "regime_tone": None},
    )

    client = TestClient(create_app())
    r = client.get("/api/live")
    assert r.status_code == 200
    body = r.json()

    assert body["spot"]["price"] is None
    assert body["watch"]["call"] is None
    assert body["watch"]["put"] is None
    assert body["decision_label"] == "Awaiting market data"
