# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Optional

from src.runtime.memory.models import MemoryItem, MemoryKind
from src.runtime.memory.store import InMemoryMemoryStore, MemoryStore, create_memory_store


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


class MemoryService:
    """Long-term memory data plane. Prompt injection stays in ContextInjectMiddleware."""

    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self._store = store or InMemoryMemoryStore()

    def write(
        self,
        *,
        user_id: str,
        kind: MemoryKind,
        content: str,
        source: str = "",
        confidence: float = 0.6,
    ) -> Optional[MemoryItem]:
        text = (content or "").strip()
        if not user_id or not text:
            return None
        item = MemoryItem(
            user_id=user_id,
            kind=kind,
            content=text[:1000],
            source=source,
            confidence=max(0.0, min(confidence, 1.0)),
        )
        return self._store.put(item)

    def retrieve(
        self,
        user_id: str,
        query: str = "",
        *,
        top_k: int = 5,
        token_budget: int = 400,
        kinds: Optional[list[MemoryKind]] = None,
    ) -> list[MemoryItem]:
        items = self._store.list_for_user(user_id)
        if kinds:
            items = [item for item in items if item.kind in kinds]
        ranked = sorted(
            items,
            key=lambda item: (_score(item.content, query), item.confidence),
            reverse=True,
        )
        selected: list[MemoryItem] = []
        used = 0
        for item in ranked:
            cost = estimate_tokens(item.content)
            if selected and used + cost > token_budget:
                continue
            selected.append(item)
            used += cost
            if len(selected) >= top_k:
                break
        return selected

    def format_context(self, items: list[MemoryItem]) -> str:
        if not items:
            return ""
        lines = ["# Long-term Memory"]
        for item in items:
            lines.append(f"- [{item.kind.value}] {item.content}")
        return "\n".join(lines)

    def clear(self, user_id: Optional[str] = None) -> None:
        self._store.clear(user_id)


def _score(content: str, query: str) -> float:
    if not query:
        return 0.0
    haystack = content.lower()
    tokens = [token for token in query.lower().replace("，", " ").split() if token]
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in haystack)
    return hits / len(tokens)


_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    global _service
    if _service is None:
        _service = MemoryService(store=create_memory_store())
    return _service


def set_memory_service(service: Optional[MemoryService]) -> None:
    global _service
    _service = service
