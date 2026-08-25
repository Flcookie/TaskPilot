# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from typing import Any

from src.runtime.middleware.base import RuntimeContext, RuntimeMiddleware
from src.runtime.tools.result import ToolResult
from src.utils.log_sanitizer import sanitize_log_input, sanitize_tool_name

logger = logging.getLogger(__name__)


class AuditMiddleware(RuntimeMiddleware):
    name = "audit"

    def before_task(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        self._emit(ctx, "audit", {"hook": "before_task", **_safe(payload)})
        return payload

    def after_task(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        self._emit(ctx, "audit", {"hook": "after_task", **_safe(payload)})
        return payload

    def before_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        tool_name = sanitize_tool_name(payload.get("name") or ctx.tool_name or "")
        logger.info("Tool %s starting", tool_name)
        self._emit(
            ctx,
            "audit",
            {
                "hook": "before_tool",
                "tool": tool_name,
                "args": _summarize_args(payload.get("args")),
            },
        )
        return payload

    def after_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        result = payload.get("result")
        ok = result.ok if isinstance(result, ToolResult) else True
        self._emit(
            ctx,
            "audit",
            {
                "hook": "after_tool",
                "tool": payload.get("name") or ctx.tool_name,
                "ok": ok,
            },
        )
        return payload

    def on_error(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        self._emit(
            ctx,
            "audit",
            {
                "hook": "on_error",
                "tool": payload.get("name") or ctx.tool_name,
                "error": sanitize_log_input(str(payload.get("error") or ""), max_length=200),
            },
        )
        return payload

    def _emit(self, ctx: RuntimeContext, event_type: str, data: dict[str, Any]) -> None:
        if not ctx.task_id:
            return
        try:
            from src.runtime.task.service import get_task_service

            get_task_service().append_event(ctx.task_id, event_type, data)
        except Exception:
            logger.debug("Skip audit event; task store unavailable", exc_info=True)


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key in {"status", "task_id", "node"}
    }


def _summarize_args(args: Any) -> Any:
    if args is None:
        return None
    text = sanitize_log_input(str(args), max_length=200)
    return text
