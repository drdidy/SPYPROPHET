from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_cache

router = APIRouter(prefix="/journal", tags=["journal"])
logger = logging.getLogger("spyprophet.api.journal")

JOURNAL_PATH_ENV = "JOURNAL_PATH"
JOURNAL_DEFAULT_PATH = "data/signal_journal.json"


def _journal_path() -> Path:
    return Path(os.getenv(JOURNAL_PATH_ENV, JOURNAL_DEFAULT_PATH))


def _load_entries() -> list[dict]:
    """Read the journal file and return JSON-friendly dicts.

    We delegate to ``app.load_signal_journal`` and ``app.journal_entry_to_dict``
    so the entry shape stays in lock-step with the Streamlit terminal —
    no risk of fields drifting between the two surfaces.
    """
    path = _journal_path()
    if not path.exists():
        return []
    try:
        from app import (
            journal_entry_to_dict,
            load_signal_journal,
        )

        entries = load_signal_journal(str(path))
        return [journal_entry_to_dict(e) for e in entries]
    except Exception as exc:
        logger.warning("journal load failed: %s", type(exc).__name__)
        # Fall back to raw JSON read if the dataclass conversion fails.
        try:
            import json

            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as exc2:  # pragma: no cover
            logger.error("journal raw read failed: %s", type(exc2).__name__)
        return []


@router.get("")
def list_journal(
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    """Read-only journal listing.

    Returns the most recent entries first (the JSON file is stored
    chronologically in append order, so we reverse here). Pagination
    via ``limit`` / ``offset``. Total count is always reported so the
    UI can render a ``N of M`` indicator.

    Writes are intentionally not exposed yet — those need a persistent
    disk on Render plus deduplication via ``upsert_journal_entry``;
    coming in the next iteration.
    """
    cache = get_cache()
    all_entries: list[dict] = cache.get_or_compute(
        "journal:entries",
        _load_entries,
        ttl=10.0,
    )
    total = len(all_entries)
    # Newest first.
    rows = list(reversed(all_entries))[offset : offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "path": str(_journal_path()),
        "entries": rows,
    }


@router.get("/summary")
def journal_summary():
    """Lightweight roll-up: total / win-rate / avg R:R for the journal page header."""
    cache = get_cache()
    entries: list[dict] = cache.get_or_compute(
        "journal:entries",
        _load_entries,
        ttl=10.0,
    )
    if not entries:
        return {
            "total": 0,
            "confirmed": 0,
            "win_rate": None,
            "avg_rr": None,
        }
    confirmed = [e for e in entries if e.get("signal_status") == "CONFIRMED"]
    target_first = sum(1 for e in confirmed if e.get("outcome") == "TARGET_FIRST")
    stop_first = sum(1 for e in confirmed if e.get("outcome") == "STOP_FIRST")
    decided = target_first + stop_first
    win_rate = (target_first / decided) if decided else None
    rrs = [e.get("rr_ratio") for e in confirmed if isinstance(e.get("rr_ratio"), int | float)]
    avg_rr = (sum(rrs) / len(rrs)) if rrs else None
    return {
        "total": len(entries),
        "confirmed": len(confirmed),
        "target_first": target_first,
        "stop_first": stop_first,
        "win_rate": win_rate,
        "avg_rr": avg_rr,
    }


@router.post("/refresh")
def refresh_journal():
    """Invalidate the cached entries so the next read hits disk.

    Useful after copying a fresh signal_journal.json into the persistent
    disk via Render Shell — saves a deploy cycle.
    """
    cache = get_cache()
    cache.clear()
    return {"status": "ok"}


class ImportRequest(BaseModel):
    entries: list[dict]
    replace: bool = False


@router.post("/import")
def import_journal(payload: ImportRequest):
    """Import journal entries onto the persistent disk.

    By default, merges (upserts) the imported entries into whatever's
    already on disk — same id wins, no duplicates. Pass ``replace=true``
    to wipe the file and write the imported list as-is (useful when
    migrating off the Streamlit terminal for the first time).

    The journal file lives at ``$JOURNAL_PATH`` (default
    ``data/signal_journal.json``) which on the Render deploy is mounted
    at ``/app/data`` from the persistent SSD added to the service.
    """
    if not isinstance(payload.entries, list):
        raise HTTPException(status_code=400, detail="entries must be a list")

    target = _journal_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        from app import (
            journal_entry_from_dict,
            save_signal_journal,
            upsert_journal_entry,
        )
    except Exception as exc:
        logger.error("journal import imports failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Journal engine unavailable.") from exc

    # Convert incoming dicts → JournalEntry, skipping malformed rows
    incoming_entries = []
    skipped = 0
    for raw in payload.entries:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        try:
            incoming_entries.append(journal_entry_from_dict(raw))
        except Exception as exc:
            logger.warning("journal import row skip: %s", type(exc).__name__)
            skipped += 1

    if payload.replace:
        merged = incoming_entries
    else:
        existing = []
        if target.exists():
            try:
                existing_dicts = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(existing_dicts, list):
                    for r in existing_dicts:
                        try:
                            existing.append(journal_entry_from_dict(r))
                        except Exception as exc:
                            logger.debug("journal import: skip existing row: %s", type(exc).__name__)
            except Exception:
                # Corrupt/missing — start fresh from the incoming set
                existing = []
        merged = list(existing)
        for new_entry in incoming_entries:
            merged = upsert_journal_entry(merged, new_entry)

    save_signal_journal(merged, str(target))

    cache = get_cache()
    cache.clear()

    return {
        "status": "ok",
        "imported": len(incoming_entries),
        "skipped": skipped,
        "total_after": len(merged),
        "path": str(target),
    }
