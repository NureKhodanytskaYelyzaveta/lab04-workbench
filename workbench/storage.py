"""Історія запусків у SQLite: журнал для метрик і зворотного зв'язку."""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('ask', 'team')),
    created TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT,
    llm_calls INTEGER,
    tokens INTEGER,
    seconds REAL,
    stop_reason TEXT,
    rating INTEGER CHECK (rating IN (0, 1)),
    saved_path TEXT,
    details TEXT
)"""

LIST_COLUMNS = ("id, kind, created, input, llm_calls, tokens, seconds, "
                "stop_reason, rating, saved_path")


class HistoryStore:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._update(SCHEMA, ())

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def add(self, kind: str, input_text: str, output: str, llm_calls: int, tokens: int,
            seconds: float, stop_reason: str = "", details: dict | None = None) -> str:
        run_id = uuid.uuid4().hex[:12]
        db = self._connect()
        try:
            with db:  # транзакція: commit або rollback
                db.execute(
                    "INSERT INTO runs (id, kind, created, input, output, llm_calls, tokens,"
                    " seconds, stop_reason, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, kind, datetime.now().isoformat(timespec="seconds"), input_text,
                     output, llm_calls, tokens, seconds, stop_reason,
                     json.dumps(details or {}, ensure_ascii=False, default=str)))
        finally:
            db.close()
        return run_id

    def _update(self, sql: str, params: tuple) -> None:
        db = self._connect()
        try:
            with db:
                db.execute(sql, params)
        finally:
            db.close()

    def rate(self, run_id: str, rating: int) -> None:
        self._update("UPDATE runs SET rating = ? WHERE id = ?", (rating, run_id))

    def mark_saved(self, run_id: str, path: str) -> None:
        self._update("UPDATE runs SET saved_path = ? WHERE id = ?", (path, run_id))

    def get(self, run_id: str) -> dict | None:
        db = self._connect()
        try:
            row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        finally:
            db.close()
        return dict(row) if row else None

    def list(self, limit: int = 100) -> list[dict]:
        db = self._connect()
        try:
            rows = db.execute(f"SELECT {LIST_COLUMNS} FROM runs "
                              "ORDER BY created DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        finally:
            db.close()
        return [dict(r) for r in rows]

    def summary(self) -> dict:
        db = self._connect()
        try:
            row = db.execute(
                "SELECT COUNT(*) AS runs, AVG(llm_calls) AS avg_calls,"
                " AVG(seconds) AS avg_seconds, SUM(tokens) AS tokens,"
                " AVG(rating) AS positive_share,"
                " SUM(saved_path IS NOT NULL) AS saved FROM runs").fetchone()
        finally:
            db.close()
        return dict(row)
