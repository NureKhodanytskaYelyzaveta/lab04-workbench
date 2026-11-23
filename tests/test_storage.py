"""Журнал запусків SQLite: схема, оцінки, метрики."""
import sqlite3

import pytest

from workbench.storage import HistoryStore


@pytest.fixture
def history(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "history.db")


def test_add_and_get_roundtrip(history):
    run_id = history.add("team", "запит", "звіт", 4, 100, 1.5, "approved", {"drafts": 1})
    row = history.get(run_id)
    assert row["kind"] == "team" and row["llm_calls"] == 4 and row["stop_reason"] == "approved"
    assert row["rating"] is None and row["saved_path"] is None


def test_schema_rejects_invalid_kind_and_rating(history):
    with pytest.raises(sqlite3.IntegrityError):
        history.add("other", "x", "y", 1, 0, 0.1)
    run_id = history.add("ask", "x", "y", 1, 0, 0.1)
    with pytest.raises(sqlite3.IntegrityError):
        history.rate(run_id, 5)


def test_summary_counts_only_rated_runs_in_positive_share(history):
    a = history.add("team", "a", "r", 4, 10, 2.0)
    b = history.add("team", "b", "r", 6, 20, 4.0)
    history.add("ask", "c", "r", 2, 0, 0.0)  # без оцінки
    history.rate(a, 1)
    history.rate(b, 0)
    history.mark_saved(a, "/vault/Inbox/a.md")
    s = history.summary()
    assert s["runs"] == 3 and s["saved"] == 1
    assert s["positive_share"] == 0.5
    assert s["avg_calls"] == 4.0 and s["tokens"] == 30


def test_list_is_newest_first(history):
    first = history.add("ask", "перший", "r", 1, 0, 0.1)
    second = history.add("ask", "другий", "r", 1, 0, 0.1)
    assert [r["id"] for r in history.list()] == [second, first]
