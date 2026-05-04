from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


def test_health_ok_when_secrets_missing(monkeypatch):
    for k in ("TASTYTRADE_CLIENT_ID", "TASTYTRADE_CLIENT_SECRET", "TASTYTRADE_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "spyprophet-api"
    assert body["tastytrade_configured"] is False


def test_health_reports_configured_when_secrets_present(monkeypatch):
    monkeypatch.setenv("TASTYTRADE_CLIENT_ID", "id")
    monkeypatch.setenv("TASTYTRADE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TASTYTRADE_REFRESH_TOKEN", "refresh")
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["tastytrade_configured"] is True


def test_root_endpoint_returns_pointer():
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "spyprophet-api"
