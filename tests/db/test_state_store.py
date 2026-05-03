"""Tests for SQLite-backed patrol state persistence."""

from __future__ import annotations

from pathlib import Path

from src.db import StateStore


def test_state_store_insert_get_update_delete(tmp_path: Path) -> None:
    """Stores, updates, lists, and deletes a patrol state record.

    Args:
        tmp_path: Pytest-provided temporary directory.
    """
    store = StateStore(str(tmp_path / "state.db"))
    store.upsert("abc", 12, 1)
    row1 = store.get("abc")
    assert row1 is not None
    assert row1["issue_iid"] == 12
    assert row1["patrol_count"] == 1
    first_seen = row1["last_seen"]
    store.upsert("abc", 12, 2)
    row2 = store.get("abc")
    assert row2 is not None
    assert row2["patrol_count"] == 2
    assert row2["last_seen"] >= first_seen
    all_rows = store.get_all()
    assert len(all_rows) == 1
    assert all_rows[0]["fingerprint"] == "abc"
    store.delete("abc")
    assert store.get("abc") is None
