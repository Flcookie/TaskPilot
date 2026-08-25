# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from typing import Any

from src.runtime.memory.models import MemoryKind
from src.runtime.memory.service import get_memory_service
from src.runtime.middleware.base import RuntimeContext, RuntimeMiddleware
from src.runtime.tools.result import ToolResult

logger = logging.getLogger(__name__)


class MemoryWriteMiddleware(RuntimeMiddleware):
    """Write long-term memory after tools/tasks. Does not inject into prompts."""

    name = "memory_write"

    def after_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        result = payload.get("result")
        if isinstance(result, ToolResult) and not result.ok:
            return payload
        content = _tool_text(payload)
        if not content or _looks_like_error(content):
            return payload
        self._write(
            ctx,
            payload,
            kind=MemoryKind.FACT,
            content=content,
            source=payload.get("name") or ctx.tool_name or "tool",
            confidence=0.55,
        )
        return payload

    def after_task(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        status = str(payload.get("status") or "")
        if status in {"failed", "cancelled"}:
            return payload
        user_text = payload.get("user_text") or ""
        if user_text:
            self._write(
                ctx,
                payload,
                kind=MemoryKind.BACKGROUND,
                content=f"Previous task: {user_text}",
                source="task",
                confidence=0.7,
            )
        locale = payload.get("locale")
        if locale:
            self._write(
                ctx,
                payload,
                kind=MemoryKind.PREFERENCE,
                content=f"Preferred locale is {locale}",
                source="config",
                confidence=0.8,
            )
        return payload

    def _write(
        self,
        ctx: RuntimeContext,
        payload: dict[str, Any],
        *,
        kind: MemoryKind,
        content: str,
        source: str,
        confidence: float,
    ) -> None:
        user_id = (
            payload.get("user_id")
            or ctx.extra.get("user_id")
            or payload.get("thread_id")
            or "default"
        )
        item = get_memory_service().write(
            user_id=user_id,
            kind=kind,
            content=content,
            source=source,
            confidence=confidence,
        )
        if item and ctx.task_id:
            try:
                from src.runtime.task.service import get_task_service

                get_task_service().append_event(
                    ctx.task_id,
                    "memory_write",
                    {"kind": item.kind.value, "id": item.id, "source": item.source},
                )
            except Exception:
                logger.debug("Skip memory_write event", exc_info=True)


def _tool_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, ToolResult):
        return str(result.data or "")[:500]
    content = payload.get("content")
    return str(content or "")[:500]


def _looks_like_error(content: str) -> bool:
    lowered = content.lower()
    return "error" in lowered or "exception" in lowered or "traceback" in lowered
