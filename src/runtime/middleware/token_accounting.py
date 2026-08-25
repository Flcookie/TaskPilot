# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from typing import Any

from src.runtime.middleware.base import RuntimeContext, RuntimeMiddleware

logger = logging.getLogger(__name__)


class TokenAccountingMiddleware(RuntimeMiddleware):
    name = "token_accounting"

    def after_llm(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = _as_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
        completion_tokens = _as_int(
            usage.get("completion_tokens") or usage.get("output_tokens")
        )
        total_tokens = _as_int(usage.get("total_tokens"))
        if total_tokens is None:
            if prompt_tokens is None and completion_tokens is None:
                content = payload.get("content")
                if isinstance(content, str) and content:
                    total_tokens = max(1, len(content) // 4)
            else:
                total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

        record = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated": not bool(usage),
            "node": ctx.node or payload.get("langgraph_node") or payload.get("agent"),
        }
        payload["token_usage"] = record
        self._emit(ctx, record)
        return payload

    def _emit(self, ctx: RuntimeContext, record: dict[str, Any]) -> None:
        if not ctx.task_id:
            return
        try:
            from src.runtime.task.service import get_task_service

            get_task_service().append_event(ctx.task_id, "token_usage", record)
        except Exception:
            logger.debug("Skip token usage event; task store unavailable", exc_info=True)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
