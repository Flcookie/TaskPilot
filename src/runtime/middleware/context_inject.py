# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from src.runtime.memory.service import get_memory_service
from src.runtime.middleware.base import RuntimeContext, RuntimeMiddleware


class ContextInjectMiddleware(RuntimeMiddleware):
    """The only middleware allowed to put memory into the prompt."""

    name = "context_inject"

    def before_planning(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self._inject(ctx, payload)

    def before_llm(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("memory_context"):
            return payload
        return self._inject(ctx, payload)

    def _inject(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = _user_id(ctx, payload)
        query = payload.get("user_text") or ""
        top_k = int(payload.get("memory_top_k") or 5)
        token_budget = int(payload.get("memory_token_budget") or 400)
        items = get_memory_service().retrieve(
            user_id,
            query,
            top_k=top_k,
            token_budget=token_budget,
        )
        payload["memory_context"] = get_memory_service().format_context(items)
        payload["memory_user_id"] = user_id
        ctx.extra["memory_context"] = payload["memory_context"]
        return payload


def _user_id(ctx: RuntimeContext, payload: dict[str, Any]) -> str:
    return (
        payload.get("user_id")
        or ctx.extra.get("user_id")
        or payload.get("thread_id")
        or "default"
    )
