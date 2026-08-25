# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.runtime.middleware.base import RuntimeContext, RuntimeMiddleware
from src.runtime.tools.result import ToolErrorKind, ToolResult
from src.utils.json_utils import sanitize_tool_response


class ToolGuardMiddleware(RuntimeMiddleware):
    """Second-line tool enforcement: allow-list, schema, timeout, error classification."""

    name = "tool_guard"

    def before_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name") or ctx.tool_name
        allowed = ctx.allowed_tools
        if allowed is not None and name not in allowed:
            payload["blocked"] = True
            payload["result"] = ToolResult.fail(
                f"Tool '{name}' is not in the allowed tool set",
                ToolErrorKind.PERMISSION,
                tool=name,
            )
            return payload

        args = payload.get("args")
        schema = payload.get("args_schema")
        if schema is not None and args is not None:
            try:
                if hasattr(schema, "model_validate"):
                    schema.model_validate(args)
                elif hasattr(schema, "validate"):
                    schema.validate(args)
            except (ValidationError, ValueError, TypeError) as exc:
                payload["blocked"] = True
                payload["result"] = ToolResult.fail(
                    str(exc),
                    ToolErrorKind.VALIDATION,
                    tool=name,
                )
        return payload

    def after_tool(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        result = payload.get("result")
        if isinstance(result, ToolResult) and result.ok and isinstance(result.data, str):
            result.data = sanitize_tool_response(result.data)
            payload["result"] = result
        return payload

    def on_error(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("result") is not None:
            return payload
        payload["result"] = classify_tool_error(payload.get("error"))
        return payload


def classify_tool_error(error: Any) -> ToolResult:
    if isinstance(error, ToolResult):
        return error
    if isinstance(error, TimeoutError):
        return ToolResult.fail(str(error) or "Tool timed out", ToolErrorKind.TIMEOUT)
    message = str(error) if error is not None else "Unknown tool error"
    lowered = message.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return ToolResult.fail(message, ToolErrorKind.TIMEOUT)
    if "permission" in lowered or "not allowed" in lowered or "denied" in lowered:
        return ToolResult.fail(message, ToolErrorKind.PERMISSION)
    if "validation" in lowered or "invalid" in lowered:
        return ToolResult.fail(message, ToolErrorKind.VALIDATION)
    return ToolResult.fail(message, ToolErrorKind.UPSTREAM)
