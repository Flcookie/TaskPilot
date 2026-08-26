# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from src.runtime.task.models import Task, TaskEvent

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    workflow_type TEXT NOT NULL,
    status TEXT NOT NULL,
    input TEXT NOT NULL,
    config TEXT NOT NULL,
    selected_skills TEXT NOT NULL,
    current_node TEXT,
    current_step_index INTEGER,
    plan_snapshot TEXT,
    error TEXT,
    thread_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS task_events (
    task_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (task_id, seq),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
"""


def parse_sqlite_url(url: str) -> str:
    """Parse sqlite:///relative or sqlite:////absolute URLs into a filesystem path."""
    if url.startswith("sqlite:////"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        raise ValueError(
            "Unsupported SQLite URL. Use sqlite:///relative/path or sqlite:////abs/path."
        )
    return url


class SqliteTaskStore:
    """File-backed Task / Event store. Same protocol as InMemoryTaskStore."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        logger.info("Task store using SQLite at %s", self._path)

    @classmethod
    def from_url(cls, url: str) -> "SqliteTaskStore":
        return cls(parse_sqlite_url(url))

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def put_task(self, task: Task) -> Task:
        data = task.model_dump(mode="json")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO tasks (
                    id, user_id, workflow_type, status, input, config, selected_skills,
                    current_node, current_step_index, plan_snapshot, error, thread_id,
                    created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id=excluded.user_id,
                    workflow_type=excluded.workflow_type,
                    status=excluded.status,
                    input=excluded.input,
                    config=excluded.config,
                    selected_skills=excluded.selected_skills,
                    current_node=excluded.current_node,
                    current_step_index=excluded.current_step_index,
                    plan_snapshot=excluded.plan_snapshot,
                    error=excluded.error,
                    thread_id=excluded.thread_id,
                    created_at=excluded.created_at,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at
                """,
                (
                    data["id"],
                    data.get("user_id"),
                    data["workflow_type"],
                    data["status"],
                    json.dumps(data.get("input") or {}, ensure_ascii=False),
                    json.dumps(data.get("config") or {}, ensure_ascii=False),
                    json.dumps(data.get("selected_skills") or [], ensure_ascii=False),
                    data.get("current_node"),
                    data.get("current_step_index"),
                    _dump_optional_json(data.get("plan_snapshot")),
                    data.get("error"),
                    data["thread_id"],
                    data["created_at"],
                    data.get("started_at"),
                    data.get("finished_at"),
                ),
            )
            self._conn.commit()
        return task.model_copy(deep=True)

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_task(row)

    def append_event(self, event: TaskEvent) -> TaskEvent:
        data = event.model_dump(mode="json")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO task_events (task_id, seq, ts, type, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    data["task_id"],
                    data["seq"],
                    data["ts"],
                    data["type"],
                    json.dumps(data.get("payload") or {}, ensure_ascii=False),
                ),
            )
            self._conn.commit()
        return event.model_copy(deep=True)

    def list_events(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT task_id, seq, ts, type, payload
                FROM task_events
                WHERE task_id = ? AND seq > ?
                ORDER BY seq ASC
                """,
                (task_id, after_seq),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def next_seq(self, task_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM task_events WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return int(row["max_seq"]) + 1 if row else 1


def _dump_optional_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _row_to_task(row: sqlite3.Row) -> Task:
    plan_raw = row["plan_snapshot"]
    return Task.model_validate(
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "workflow_type": row["workflow_type"],
            "status": row["status"],
            "input": json.loads(row["input"]),
            "config": json.loads(row["config"]),
            "selected_skills": json.loads(row["selected_skills"]),
            "current_node": row["current_node"],
            "current_step_index": row["current_step_index"],
            "plan_snapshot": json.loads(plan_raw) if plan_raw else None,
            "error": row["error"],
            "thread_id": row["thread_id"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }
    )


def _row_to_event(row: sqlite3.Row) -> TaskEvent:
    return TaskEvent.model_validate(
        {
            "task_id": row["task_id"],
            "seq": row["seq"],
            "ts": row["ts"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
        }
    )
