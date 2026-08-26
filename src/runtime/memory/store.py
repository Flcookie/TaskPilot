# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from threading import Lock
from typing import Optional, Protocol

from src.runtime.memory.models import MemoryItem, MemoryKind


class MemoryStore(Protocol):
    def put(self, item: MemoryItem) -> MemoryItem: ...

    def list_for_user(
        self, user_id: str, kind: Optional[MemoryKind] = None
    ) -> list[MemoryItem]: ...

    def clear(self, user_id: Optional[str] = None) -> None: ...


def create_memory_store() -> MemoryStore:
    """Build the Memory store from MEMORY_STORE_URL.

    Defaults to SQLite so preference / background / fact survive restart.
    Tests should set MEMORY_STORE_URL=memory:// (see tests/conftest.py).
    """
    from src.config.loader import get_str_env

    url = get_str_env("MEMORY_STORE_URL", "sqlite:///data/memory.sqlite")
    normalized = url.lower()
    if normalized in {"", "memory", "memory://", "inmemory"}:
        return InMemoryMemoryStore()
    if normalized.startswith("sqlite:") or "://" not in url:
        from src.runtime.memory.sqlite import SqliteMemoryStore

        if normalized.startswith("sqlite:"):
            return SqliteMemoryStore.from_url(url)
        return SqliteMemoryStore(url)
    raise ValueError(
        f"Unsupported MEMORY_STORE_URL={url!r}. Use memory:// or sqlite:///path."
    )


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, list[MemoryItem]] = {}
        self._lock = Lock()

    def put(self, item: MemoryItem) -> MemoryItem:
        with self._lock:
            cloned = item.model_copy(deep=True)
            bucket = self._items.setdefault(item.user_id, [])
            existing = next(
                (
                    idx
                    for idx, current in enumerate(bucket)
                    if current.kind == cloned.kind and current.content == cloned.content
                ),
                None,
            )
            if existing is not None:
                bucket[existing] = cloned
            else:
                bucket.append(cloned)
            return cloned.model_copy(deep=True)

    def list_for_user(
        self, user_id: str, kind: Optional[MemoryKind] = None
    ) -> list[MemoryItem]:
        with self._lock:
            items = self._items.get(user_id, [])
            selected = [
                item.model_copy(deep=True)
                for item in items
                if kind is None or item.kind == kind
            ]
            return selected

    def clear(self, user_id: Optional[str] = None) -> None:
        with self._lock:
            if user_id is None:
                self._items.clear()
            else:
                self._items.pop(user_id, None)
