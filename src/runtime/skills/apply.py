# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Optional

from src.runtime.middleware.base import RuntimeContext, get_middleware_stack


def apply_skill_selection(
    user_text: str,
    *,
    task_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    stack = get_middleware_stack()
    resolved_user = user_id
    if task_id and not resolved_user:
        try:
            from src.runtime.task.service import get_task_service

            task = get_task_service().get(task_id)
            resolved_user = task.user_id or task.thread_id
        except Exception:
            resolved_user = None
    ctx = RuntimeContext(task_id=task_id, extra={"user_id": resolved_user})
    return stack.invoke(
        "before_planning",
        ctx,
        {
            "user_text": user_text or "",
            "task_id": task_id,
            "user_id": resolved_user,
        },
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
