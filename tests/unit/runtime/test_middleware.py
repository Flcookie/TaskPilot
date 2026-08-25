# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.runtime.middleware.base import (
    MiddlewareStack,
    RuntimeContext,
    RuntimeMiddleware,
    build_default_stack,
)
from src.runtime.middleware.tool_guard import ToolGuardMiddleware
from src.runtime.task.service import TaskService, set_task_service
from src.runtime.tools.result import ToolErrorKind
from src.runtime.tools.wrapper import execute_tool


class _Recorder(RuntimeMiddleware):
    name = "recorder"

    def __init__(self) -> None:
        self.hooks: list[str] = []

    def before_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        self.hooks.append("before_tool")
        return payload

    def after_llm(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        self.hooks.append("after_llm")
        return payload


def test_middleware_hooks_are_optional():
    stack = MiddlewareStack([RuntimeMiddleware(), _Recorder()])
    payload = stack.invoke("after_llm", RuntimeContext(), {"content": "hi"})
    assert payload["content"] == "hi"


def test_disabling_one_middleware_keeps_the_stack_working():
    recorder = _Recorder()
    stack = MiddlewareStack([recorder, ToolGuardMiddleware()]).without("tool_guard")
    assert "tool_guard" not in stack.names
    result = stack.invoke("before_tool", RuntimeContext(), {"name": "demo"})
    assert result["name"] == "demo"
    assert recorder.hooks == ["before_tool"]


def test_default_stack_has_expected_layers():
    assert build_default_stack().names == [
        "audit",
        "skill",
        "token_accounting",
        "tool_guard",
    ]


def test_tool_guard_blocks_tools_outside_allow_list():
    @tool
    def secret_tool(value: str) -> str:
        """Secret tool used for allow-list tests."""
        return value

    result = execute_tool(
        secret_tool,
        {"value": "x"},
        ctx=RuntimeContext(allowed_tools=["web_search"]),
        stack=MiddlewareStack([ToolGuardMiddleware()]),
    )
    assert result.ok is False
    assert result.error_kind == ToolErrorKind.PERMISSION


def test_tool_guard_validates_schema():
    class Payload(BaseModel):
        count: int = Field(..., ge=1)

    @tool(args_schema=Payload)
    def counted_tool(count: int) -> str:
        """Return the count as text."""
        return str(count)

    result = execute_tool(
        counted_tool,
        {"count": 0},
        stack=MiddlewareStack([ToolGuardMiddleware()]),
    )
    assert result.ok is False
    assert result.error_kind == ToolErrorKind.VALIDATION


def test_tool_guard_classifies_timeout():
    @tool
    def sleepy_tool(value: str) -> str:
        """Sleep then echo the value."""
        import time

        time.sleep(0.2)
        return value

    result = execute_tool(
        sleepy_tool,
        {"value": "x"},
        stack=MiddlewareStack([ToolGuardMiddleware()]),
        timeout_seconds=0.01,
    )
    assert result.ok is False
    assert result.error_kind == ToolErrorKind.TIMEOUT


def test_audit_and_token_hooks_write_task_events():
    service = TaskService()
    set_task_service(service)
    try:
        task = service.create()
        stack = build_default_stack()
        ctx = RuntimeContext(task_id=task.id, node="planner")
        stack.invoke("before_task", ctx, {"task_id": task.id})
        stack.invoke("after_llm", ctx, {"content": "abcd", "usage": {}})
        types = [event.type for event in service.list_events(task.id)]
        assert "audit" in types
        assert "token_usage" in types
    finally:
        set_task_service(None)
