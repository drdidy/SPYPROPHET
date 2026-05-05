from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api import deps
from api.main import create_app


def _seed_journal(tmp_path: Path, monkeypatch) -> Path:
    journal = tmp_path / "signal_journal.json"
    entries = [
        {
            "journal_id": "j1",
            "created_at": "2026-05-01T09:00:00",
            "updated_at": None,
            "trade_date": "2026-05-01",
            "source": "LIVE_MANUAL",
            "signal_id": "s1",
            "signal_type": "CALL",
            "signal_status": "CONFIRMED",
            "line_name": "UA",
            "line_zone_type": "PUT_ZONE",
            "bias": "Bullish",
            "quality_grade": "A",
            "quality_score": 0.9,
            "final_decision": "TAKE",
            "action_label": "Long calls",
            "rejection_time": None,
            "entry_time": "2026-05-01T09:30:00",
            "entry_price": 622.0,
            "stop_price": 620.0,
            "target_line_name": "LD",
            "target_price": 626.0,
            "rr_ratio": 2.0,
            "outcome": "TARGET_FIRST",
            "outcome_time": "2026-05-01T11:00:00",
            "max_favorable_move": 4.0,
            "max_adverse_move": 0.5,
            "bars_to_outcome": 3,
            "selected_option_type": "CALL",
            "selected_option_strike": 624,
            "estimated_entry_mark": 1.2,
            "estimated_target_mark": 3.5,
            "estimated_profit_per_contract": 230.0,
            "provider_used": "TASTYTRADE_LIVE",
            "notes": "first signal",
            "tags": ["clean"],
        },
        {
            "journal_id": "j2",
            "created_at": "2026-05-02T09:30:00",
            "updated_at": None,
            "trade_date": "2026-05-02",
            "source": "LIVE_MANUAL",
            "signal_id": "s2",
            "signal_type": "PUT",
            "signal_status": "CONFIRMED",
            "line_name": "UD",
            "line_zone_type": "CALL_ZONE",
            "bias": "Bearish",
            "quality_grade": "B",
            "quality_score": 0.7,
            "final_decision": "TAKE",
            "action_label": "Long puts",
            "rejection_time": None,
            "entry_time": "2026-05-02T10:30:00",
            "entry_price": 624.0,
            "stop_price": 626.0,
            "target_line_name": "UA",
            "target_price": 620.0,
            "rr_ratio": 2.0,
            "outcome": "STOP_FIRST",
            "outcome_time": "2026-05-02T11:30:00",
            "max_favorable_move": 0.4,
            "max_adverse_move": 2.1,
            "bars_to_outcome": 1,
            "selected_option_type": "PUT",
            "selected_option_strike": 622,
            "estimated_entry_mark": 1.1,
            "estimated_target_mark": 2.5,
            "estimated_profit_per_contract": -110.0,
            "provider_used": "TASTYTRADE_LIVE",
            "notes": "stopped out",
            "tags": [],
        },
    ]
    journal.write_text(json.dumps(entries))
    monkeypatch.setenv("JOURNAL_PATH", str(journal))
    deps.get_cache().clear()
    return journal


def test_list_journal_returns_newest_first(tmp_path, monkeypatch):
    _seed_journal(tmp_path, monkeypatch)
    client = TestClient(create_app())
    r = client.get("/api/journal")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["entries"][0]["journal_id"] == "j2"
    assert body["entries"][1]["journal_id"] == "j1"


def test_journal_summary_computes_winrate(tmp_path, monkeypatch):
    _seed_journal(tmp_path, monkeypatch)
    client = TestClient(create_app())
    r = client.get("/api/journal/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["confirmed"] == 2
    assert body["target_first"] == 1
    assert body["stop_first"] == 1
    assert body["win_rate"] == 0.5
    assert body["avg_rr"] == 2.0


def test_journal_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("JOURNAL_PATH", str(tmp_path / "missing.json"))
    deps.get_cache().clear()
    client = TestClient(create_app())
    r = client.get("/api/journal")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    s = client.get("/api/journal/summary")
    assert s.json() == {"total": 0, "confirmed": 0, "win_rate": None, "avg_rr": None}


def test_journal_pagination(tmp_path, monkeypatch):
    _seed_journal(tmp_path, monkeypatch)
    client = TestClient(create_app())
    r = client.get("/api/journal?limit=1")
    assert r.json()["entries"][0]["journal_id"] == "j2"
    r = client.get("/api/journal?limit=1&offset=1")
    assert r.json()["entries"][0]["journal_id"] == "j1"


def test_journal_refresh_clears_cache(tmp_path, monkeypatch):
    _seed_journal(tmp_path, monkeypatch)
    client = TestClient(create_app())
    r = client.post("/api/journal/refresh")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
