from __future__ import annotations

from fastapi.testclient import TestClient

from api import deps, structure as structure_module
from api.main import create_app
from api.routes import live as live_route
from api.routes import structure as structure_route


_FAKE_PROJECTION = {
    "pivot_session": "2026-05-01",
    "as_of": "2026-05-04T19:00:00-05:00",
    "lines": [
        {
            "name": "UA",
            "label": "Upper Ascending",
            "role": "PUT_ZONE",
            "kind": "ascending",
            "zone_type": "PUT_ZONE",
            "projected_value": 729.67,
            "distance": 11.66,
        },
        {
            "name": "UD",
            "label": "Upper Descending",
            "role": "CALL_ZONE",
            "kind": "descending",
            "zone_type": "CALL_ZONE",
            "projected_value": 720.07,
            "distance": 2.06,
        },
        {
            "name": "LA",
            "label": "Lower Ascending",
            "role": "PUT_ZONE",
            "kind": "ascending",
            "zone_type": "PUT_ZONE",
            "projected_value": 724.27,
            "distance": 6.26,
        },
        {
            "name": "LD",
            "label": "Lower Descending",
            "role": "CALL_ZONE",
            "kind": "descending",
            "zone_type": "CALL_ZONE",
            "projected_value": 716.67,
            "distance": -1.34,
        },
    ],
    "closest_above": {
        "name": "UD",
        "label": "Upper Descending",
        "role": "CALL_ZONE",
        "kind": "descending",
        "zone_type": "CALL_ZONE",
        "projected_value": 720.07,
        "distance": 2.06,
    },
    "closest_below": {
        "name": "LD",
        "label": "Lower Descending",
        "role": "CALL_ZONE",
        "kind": "descending",
        "zone_type": "CALL_ZONE",
        "projected_value": 716.67,
        "distance": -1.34,
    },
    "closest_descending_above": {
        "name": "UD",
        "label": "Upper Descending",
        "role": "CALL_ZONE",
        "kind": "descending",
        "zone_type": "CALL_ZONE",
        "projected_value": 720.07,
        "distance": 2.06,
    },
    "closest_descending_below": {
        "name": "LD",
        "label": "Lower Descending",
        "role": "CALL_ZONE",
        "kind": "descending",
        "zone_type": "CALL_ZONE",
        "projected_value": 716.67,
        "distance": -1.34,
    },
}


def test_structure_endpoint_returns_projection(monkeypatch):
    deps.get_cache().clear()
    monkeypatch.setattr(
        structure_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 718.01, "change": 2.84, "change_pct": 0.4},
    )
    monkeypatch.setattr(
        structure_route,
        "compute_structure_projection",
        lambda spot: _FAKE_PROJECTION,
    )

    client = TestClient(create_app())
    r = client.get("/api/structure/spy")
    assert r.status_code == 200
    body = r.json()
    assert body["pivot_session"] == "2026-05-01"
    assert len(body["lines"]) == 4
    assert body["closest_above"]["name"] == "UD"
    assert body["closest_below"]["name"] == "LD"


def test_structure_endpoint_502_when_data_unavailable(monkeypatch):
    deps.get_cache().clear()
    monkeypatch.setattr(
        structure_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": None, "change": None, "change_pct": None},
    )
    monkeypatch.setattr(
        structure_route,
        "compute_structure_projection",
        lambda spot: None,
    )

    client = TestClient(create_app())
    r = client.get("/api/structure/spy")
    assert r.status_code == 502


def test_live_endpoint_picks_call_setup_when_below_is_closer(monkeypatch):
    """LD is at 716.67 (-1.34), UD is at 720.07 (+2.06). LD closer →
    CALL setup with trigger=LD, target=closest_above (UD)."""
    deps.get_cache().clear()
    monkeypatch.setattr(
        live_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 718.01, "change": 2.84, "change_pct": 0.4},
    )
    monkeypatch.setattr(
        live_route,
        "fetch_vix_snapshot",
        lambda: {"value": 18.29, "regime": "Moderate", "regime_tone": "green"},
    )
    monkeypatch.setattr(
        live_route,
        "compute_structure_projection",
        lambda spot: _FAKE_PROJECTION,
    )

    client = TestClient(create_app())
    r = client.get("/api/live")
    assert r.status_code == 200
    body = r.json()

    assert body["spot"]["price"] == 718.01
    assert body["trigger"] is not None
    # Closest descending line is LD at -1.34, so CALL setup
    assert body["trigger"]["line_code"] == "LD"
    assert body["trigger"]["setup"] == "CALL"
    assert body["trigger"]["value"] == 716.67
    # Target = closest_above (UD)
    assert body["target"] is not None
    assert body["target"]["line_code"] == "UD"
    assert body["target"]["value"] == 720.07
    # Stop is below LD with 0.20 buffer
    assert body["stop"] == 716.47
    assert "CALL setup" in body["decision_label"]
    assert "above 716.67" in body["decision_label"]


def test_live_endpoint_picks_put_setup_when_above_is_closer(monkeypatch):
    """Move spot lower so UD becomes the closest descending line; expect
    PUT setup with trigger=UD, target=closest_below (LD)."""
    deps.get_cache().clear()
    # UD at 720.07, LD at 716.67. Set spot at 720 → UD distance +0.07,
    # LD distance -3.33. Closest descending = UD → PUT setup.
    projection = dict(_FAKE_PROJECTION)
    projection["closest_descending_above"] = {
        **_FAKE_PROJECTION["closest_descending_above"],
        "distance": 0.07,
    }
    projection["closest_descending_below"] = {
        **_FAKE_PROJECTION["closest_descending_below"],
        "distance": -3.33,
    }

    monkeypatch.setattr(
        live_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 720.00, "change": 4.00, "change_pct": 0.55},
    )
    monkeypatch.setattr(
        live_route,
        "fetch_vix_snapshot",
        lambda: {"value": 18.29, "regime": "Moderate", "regime_tone": "green"},
    )
    monkeypatch.setattr(live_route, "compute_structure_projection", lambda spot: projection)

    client = TestClient(create_app())
    r = client.get("/api/live")
    body = r.json()
    assert body["trigger"]["line_code"] == "UD"
    assert body["trigger"]["setup"] == "PUT"
    # Stop above UD with 0.20 buffer
    assert body["stop"] == 720.27
    assert "PUT setup" in body["decision_label"]
    assert "below 720.07" in body["decision_label"]


def test_live_endpoint_falls_back_when_structure_unavailable(monkeypatch):
    deps.get_cache().clear()
    monkeypatch.setattr(
        live_route,
        "fetch_spy_spot_snapshot",
        lambda: {"price": 718.01, "change": 2.84, "change_pct": 0.4},
    )
    monkeypatch.setattr(
        live_route,
        "fetch_vix_snapshot",
        lambda: {"value": 18.29, "regime": "Moderate", "regime_tone": "green"},
    )
    monkeypatch.setattr(live_route, "compute_structure_projection", lambda spot: None)

    client = TestClient(create_app())
    r = client.get("/api/live")
    assert r.status_code == 200
    body = r.json()
    assert body["trigger"] is None
    assert body["target"] is None
    # Spot still flows so the page renders SPY price.
    assert body["spot"]["price"] == 718.01
