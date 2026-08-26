# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from src.runtime.middleware.base import RuntimeContext, get_middleware_stack
from src.runtime.task.models import TaskEvent
from src.runtime.task.service import TaskService

RUNTIME_CLIENT_EVENTS = frozenset({"skill_selected", "skill_loaded", "token_usage"})


def parse_sse_chunk(chunk: str) -> tuple[Optional[str], dict[str, Any]]:
    event_type: Optional[str] = None
    data: dict[str, Any] = {}
    if not chunk:
        return event_type, data

    for line in chunk.splitlines():
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            raw = line[len("data:") :].strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                data = {"raw": raw}
            else:
                if isinstance(parsed, dict):
                    data = parsed
                else:
                    data = {"value": parsed}
    return event_type, data


def format_sse(event_type: str, payload: dict[str, Any], seq: Optional[int] = None) -> str:
    body = dict(payload)
    if seq is not None:
        body.setdefault("event_id", seq)
    return f"event: {event_type}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"


def replay_events_as_sse(events: list[TaskEvent]) -> list[str]:
    return [format_sse(event.type, event.payload, seq=event.seq) for event in events]


def _collect_runtime_sse(
    service: TaskService, task_id: str, after_seq: int
) -> tuple[list[str], int]:
    extras: list[str] = []
    latest = after_seq
    for event in service.list_events(task_id, after_seq=after_seq):
        latest = event.seq
        if event.type in RUNTIME_CLIENT_EVENTS:
            extras.append(format_sse(event.type, event.payload, seq=event.seq))
    return extras, latest


async def persist_workflow_stream(
    service: TaskService,
    task_id: str,
    workflow_events: AsyncIterator[str],
) -> AsyncIterator[str]:
    """Start a task, dual-write each SSE chunk to EventStore, then close the lifecycle."""
    service.start(task_id)
    task = service.get(task_id)
    user_id = task.user_id or task.thread_id
    user_text = ""
    messages = task.input.get("messages") or []
    if messages:
        last = messages[-1]
        if isinstance(last, dict):
            user_text = str(last.get("content") or "")
    opened = service.append_event(
        task_id,
        "task",
        {
            "task_id": task_id,
            "thread_id": task.thread_id,
            "status": task.status.value,
        },
    )
    yield format_sse("task", opened.payload, seq=opened.seq)
    last_seq = opened.seq
    stack = get_middleware_stack()
    ctx = RuntimeContext(task_id=task_id, extra={"user_id": user_id})
    await stack.ainvoke("before_task", ctx, {"task_id": task_id, "user_id": user_id})
    first_chunk = True
    try:
        async for chunk in workflow_events:
            if first_chunk:
                first_chunk = False
                extras, last_seq = _collect_runtime_sse(service, task_id, last_seq)
                for extra in extras:
                    yield extra
            event_type, payload = parse_sse_chunk(chunk)
            if event_type:
                service.apply_stream_event(task_id, event_type, payload)
                if event_type in {"message_chunk", "tool_calls"}:
                    ctx.node = payload.get("langgraph_node") or payload.get("agent")
                    await stack.ainvoke("after_llm", ctx, payload)
                if event_type == "tool_call_result":
                    await stack.ainvoke(
                        "after_tool",
                        ctx,
                        {
                            "name": payload.get("name") or payload.get("tool_name"),
                            "content": payload.get("content"),
                            "user_id": user_id,
                        },
                    )
            extras, last_seq = _collect_runtime_sse(service, task_id, last_seq)
            for extra in extras:
                yield extra
            yield chunk
        extras, last_seq = _collect_runtime_sse(service, task_id, last_seq)
        for extra in extras:
            yield extra
        finished = service.finish_if_running(task_id)
        await stack.ainvoke(
            "after_task",
            ctx,
            {
                "task_id": task_id,
                "status": finished.status.value,
                "user_id": user_id,
                "user_text": user_text,
                "locale": (task.config or {}).get("locale"),
            },
        )
        extras, _ = _collect_runtime_sse(service, task_id, last_seq)
        for extra in extras:
            yield extra
    except Exception as exc:
        current = service.get(task_id)
        if current.status.value != "cancelled":
            failed = service.mark_failed(task_id, str(exc))
            await stack.ainvoke("on_error", ctx, {"error": exc, "status": failed.status.value})
        raise
