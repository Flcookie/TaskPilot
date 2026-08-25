# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


HOOKS = (
    "before_task",
    "after_task",
    "before_node",
    "after_node",
    "before_llm",
    "after_llm",
    "before_planning",
    "before_tool",
    "after_tool",
    "on_error",
)


@dataclass
class RuntimeContext:
    task_id: Optional[str] = None
    node: Optional[str] = None
    tool_name: Optional[str] = None
    allowed_tools: Optional[list[str]] = None
    extra: dict[str, Any] = field(default_factory=dict)


class RuntimeMiddleware:
    """Hook-based middleware. Override only the points you care about."""

    name = "runtime"

    def before_task(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def after_task(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def before_node(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def after_node(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def before_llm(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def after_llm(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def before_planning(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def before_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def after_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def on_error(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    async def abefore_task(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.before_task(ctx, payload)

    async def aafter_task(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.after_task(ctx, payload)

    async def abefore_node(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.before_node(ctx, payload)

    async def aafter_node(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.after_node(ctx, payload)

    async def abefore_llm(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.before_llm(ctx, payload)

    async def aafter_llm(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.after_llm(ctx, payload)

    async def abefore_planning(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.before_planning(ctx, payload)

    async def abefore_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.before_tool(ctx, payload)

    async def aafter_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.after_tool(ctx, payload)

    async def aon_error(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        return self.on_error(ctx, payload)


class MiddlewareStack:
    def __init__(self, middlewares: Optional[Iterable[RuntimeMiddleware]] = None) -> None:
        self._middlewares = list(middlewares or [])

    @property
    def names(self) -> list[str]:
        return [middleware.name for middleware in self._middlewares]

    def without(self, name: str) -> "MiddlewareStack":
        return MiddlewareStack(m for m in self._middlewares if m.name != name)

    def invoke(self, hook: str, ctx: RuntimeContext, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if hook not in HOOKS:
            raise ValueError(f"Unknown middleware hook: {hook}")
        current = dict(payload or {})
        for middleware in self._middlewares:
            current = getattr(middleware, hook)(ctx, current) or current
        return current

    async def ainvoke(
        self, hook: str, ctx: RuntimeContext, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        if hook not in HOOKS:
            raise ValueError(f"Unknown middleware hook: {hook}")
        current = dict(payload or {})
        for middleware in self._middlewares:
            current = await getattr(middleware, f"a{hook}")(ctx, current) or current
        return current


_stack: Optional[MiddlewareStack] = None


def build_default_stack() -> MiddlewareStack:
    from src.runtime.middleware.audit import AuditMiddleware
    from src.runtime.middleware.context_inject import ContextInjectMiddleware
    from src.runtime.middleware.memory_write import MemoryWriteMiddleware
    from src.runtime.middleware.skill import SkillMiddleware
    from src.runtime.middleware.token_accounting import TokenAccountingMiddleware
    from src.runtime.middleware.tool_guard import ToolGuardMiddleware

    return MiddlewareStack(
        [
            AuditMiddleware(),
            SkillMiddleware(),
            ContextInjectMiddleware(),
            TokenAccountingMiddleware(),
            ToolGuardMiddleware(),
            MemoryWriteMiddleware(),
        ]
    )


def get_middleware_stack() -> MiddlewareStack:
    global _stack
    if _stack is None:
        _stack = build_default_stack()
    return _stack


def set_middleware_stack(stack: Optional[MiddlewareStack]) -> None:
    global _stack
    _stack = stack
