# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from threading import Lock
from typing import Optional, Protocol

from src.runtime.task.models import Task, TaskEvent


class TaskStore(Protocol):
    def put_task(self, task: Task) -> Task: ...

    def get_task(self, task_id: str) -> Optional[Task]: ...

    def append_event(self, event: TaskEvent) -> TaskEvent: ...

    def list_events(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]: ...

    def next_seq(self, task_id: str) -> int: ...


class InMemoryTaskStore:
    """Process-local store. Swap later for SQLite / Postgres without changing TaskService."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._events: dict[str, list[TaskEvent]] = {}
        self._lock = Lock()

    def put_task(self, task: Task) -> Task:
        with self._lock:
            cloned = task.model_copy(deep=True)
            self._tasks[task.id] = cloned
            self._events.setdefault(task.id, [])
            return cloned.model_copy(deep=True)

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.model_copy(deep=True) if task else None

    def append_event(self, event: TaskEvent) -> TaskEvent:
        with self._lock:
            events = self._events.setdefault(event.task_id, [])
            cloned = event.model_copy(deep=True)
            events.append(cloned)
            return cloned.model_copy(deep=True)

    def list_events(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
        with self._lock:
            events = self._events.get(task_id, [])
            return [
                event.model_copy(deep=True) for event in events if event.seq > after_seq
            ]

    def next_seq(self, task_id: str) -> int:
        with self._lock:
            events = self._events.get(task_id, [])
            return (events[-1].seq + 1) if events else 1

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._events.clear()
