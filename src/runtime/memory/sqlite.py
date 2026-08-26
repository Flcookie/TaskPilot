# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Optional

from src.runtime.memory.models import MemoryItem, MemoryKind
from src.runtime.sqlite_url import parse_sqlite_url

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, kind, content)
);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
"""


class SqliteMemoryStore:
    """File-backed memory store. Same protocol as InMemoryMemoryStore."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        logger.info("Memory store using SQLite at %s", self._path)

    @classmethod
    def from_url(cls, url: str) -> "SqliteMemoryStore":
        return cls(parse_sqlite_url(url))

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def put(self, item: MemoryItem) -> MemoryItem:
        data = item.model_dump(mode="json")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memories (id, user_id, kind, content, source, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, kind, content) DO UPDATE SET
                    id=excluded.id,
                    source=excluded.source,
                    confidence=excluded.confidence,
                    created_at=excluded.created_at
                """,
                (
                    data["id"],
                    data["user_id"],
                    data["kind"],
                    data["content"],
                    data.get("source") or "",
                    data["confidence"],
                    data["created_at"],
                ),
            )
            self._conn.commit()
        return item.model_copy(deep=True)

    def list_for_user(
        self, user_id: str, kind: Optional[MemoryKind] = None
    ) -> list[MemoryItem]:
        with self._lock:
            if kind is None:
                rows = self._conn.execute(
                    "SELECT * FROM memories WHERE user_id = ? ORDER BY created_at ASC",
                    (user_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE user_id = ? AND kind = ?
                    ORDER BY created_at ASC
                    """,
                    (user_id, kind.value),
                ).fetchall()
        return [_row_to_item(row) for row in rows]

    def clear(self, user_id: Optional[str] = None) -> None:
        with self._lock:
            if user_id is None:
                self._conn.execute("DELETE FROM memories")
            else:
                self._conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
            self._conn.commit()


def _row_to_item(row: sqlite3.Row) -> MemoryItem:
    return MemoryItem.model_validate(
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "kind": row["kind"],
            "content": row["content"],
            "source": row["source"],
            "confidence": row["confidence"],
            "created_at": row["created_at"],
        }
    )
