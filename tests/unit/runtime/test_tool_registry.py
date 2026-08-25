# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from langchain_core.tools import tool

from src.runtime.middleware.base import MiddlewareStack, RuntimeContext
from src.runtime.tools.registry import ToolRegistry, get_tool_registry, set_tool_registry
from src.runtime.tools.result import ToolResult
from src.runtime.tools.wrapper import execute_tool, wrap_tool


def test_registry_registers_and_binds_by_name():
    @tool
    def echo_tool(text: str) -> str:
        """Echo text."""
        return text

    registry = ToolRegistry()
    registry.register("echo", echo_tool, timeout_seconds=5)
    assert "echo" in registry.names()
    tools = registry.bind(["echo"])
    assert len(tools) == 1
    assert tools[0].name == "echo_tool"


def test_bind_hides_tools_not_in_allowed_list():
    @tool
    def keep_tool(text: str) -> str:
        """Visible tool."""
        return text

    @tool
    def hide_tool(text: str) -> str:
        """Hidden tool."""
        return text

    registry = ToolRegistry()
    registry.register("keep", keep_tool)
    registry.register("hide", hide_tool)
    tools = registry.bind(["keep", "hide"], allowed_tools=["keep"])
    assert [item.name for item in tools] == ["keep_tool"]


def test_builtin_registry_exposes_native_tools():
    set_tool_registry(None)
    registry = get_tool_registry()
    try:
        names = registry.names()
        assert "web_search" in names
        assert "crawl" in names
        assert "python_repl" in names
    finally:
        set_tool_registry(None)


def test_successful_tool_keeps_original_payload():
    @tool
    def echo_tool(text: str) -> str:
        """Echo text."""
        return text

    result = execute_tool(echo_tool, {"text": "hello"}, stack=MiddlewareStack())
    assert result == ToolResult.success("hello", tool="echo_tool")
    assert result.to_agent_content() == "hello"


def test_wrapped_tool_returns_structured_error_on_failure():
    @tool
    def boom_tool(text: str) -> str:
        """Always fail."""
        raise RuntimeError("upstream exploded")

    wrapped = wrap_tool(boom_tool, ctx=RuntimeContext(), stack=MiddlewareStack())
    content = wrapped.invoke({"text": "x"})
    assert content["ok"] is False
    assert content["error_kind"] == "upstream"
