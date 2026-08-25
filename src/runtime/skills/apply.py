# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Optional

from src.runtime.middleware.base import RuntimeContext, get_middleware_stack


def apply_skill_selection(
    user_text: str,
    *,
    task_id: Optional[str] = None,
) -> dict[str, Any]:
    stack = get_middleware_stack()
    ctx = RuntimeContext(task_id=task_id)
    return stack.invoke(
        "before_planning",
        ctx,
        {"user_text": user_text or "", "task_id": task_id},
    )


def extract_user_text(messages: list[Any]) -> str:
    for message in reversed(messages or []):
        if isinstance(message, dict):
            if message.get("role") == "user":
                content = message.get("content", "")
                return content if isinstance(content, str) else str(content)
        elif getattr(message, "type", None) == "human":
            return str(getattr(message, "content", ""))
    if messages:
        last = messages[-1]
        if isinstance(last, dict):
            content = last.get("content", "")
            return content if isinstance(content, str) else str(content)
    return ""
