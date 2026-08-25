# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Optional

from langchain_core.tools import BaseTool, StructuredTool

from src.runtime.middleware.base import MiddlewareStack, RuntimeContext, get_middleware_stack
from src.runtime.middleware.tool_guard import classify_tool_error
from src.runtime.tools.result import ToolResult


def execute_tool(
    tool: BaseTool,
    args: dict[str, Any],
    *,
    ctx: Optional[RuntimeContext] = None,
    stack: Optional[MiddlewareStack] = None,
    timeout_seconds: Optional[float] = None,
) -> ToolResult:
    stack = stack or get_middleware_stack()
    ctx = ctx or RuntimeContext(tool_name=getattr(tool, "name", None))
    ctx.tool_name = getattr(tool, "name", ctx.tool_name)

    payload: dict[str, Any] = {
        "name": ctx.tool_name,
        "args": args,
        "args_schema": getattr(tool, "args_schema", None),
    }
    payload = stack.invoke("before_tool", ctx, payload)
    if payload.get("blocked"):
        result = payload.get("result")
        if not isinstance(result, ToolResult):
            result = classify_tool_error(payload.get("error") or "Tool blocked")
        stack.invoke("after_tool", ctx, {**payload, "result": result})
        return result

    try:
        raw = _invoke_with_timeout(tool, args, timeout_seconds)
        result = ToolResult.success(raw, tool=ctx.tool_name)
    except Exception as exc:
        timeout_exc = isinstance(exc, (TimeoutError, FuturesTimeout))
        error = TimeoutError(str(exc) or "Tool timed out") if timeout_exc else exc
        error_payload = stack.invoke(
            "on_error",
            ctx,
            {"name": ctx.tool_name, "error": error},
        )
        result = error_payload.get("result")
        if not isinstance(result, ToolResult):
            result = classify_tool_error(error)

    after = stack.invoke("after_tool", ctx, {**payload, "result": result})
    final = after.get("result")
    return final if isinstance(final, ToolResult) else result


def wrap_tool(
    tool: BaseTool,
    *,
    ctx: Optional[RuntimeContext] = None,
    stack: Optional[MiddlewareStack] = None,
    timeout_seconds: Optional[float] = None,
) -> BaseTool:
    def _func(**kwargs: Any) -> Any:
        """Execute a registered tool through the runtime middleware stack."""
        result = execute_tool(
            tool,
            kwargs,
            ctx=ctx or RuntimeContext(tool_name=tool.name),
            stack=stack,
            timeout_seconds=timeout_seconds,
        )
        return result.to_agent_content()

    async def _afunc(**kwargs: Any) -> Any:
        return _func(**kwargs)

    return StructuredTool.from_function(
        name=tool.name,
        description=getattr(tool, "description", "") or tool.name,
        func=_func,
        coroutine=_afunc,
        args_schema=getattr(tool, "args_schema", None),
    )


def _invoke_with_timeout(
    tool: BaseTool, args: dict[str, Any], timeout_seconds: Optional[float]
) -> Any:
    if not timeout_seconds:
        return tool.invoke(args)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(tool.invoke, args)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeout as exc:
            raise TimeoutError(f"Tool '{getattr(tool, 'name', 'unknown')}' timed out") from exc
