# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from src.runtime.task.models import TaskEvent
from src.runtime.task.service import TaskService


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


async def persist_workflow_stream(
    service: TaskService,
    task_id: str,
    workflow_events: AsyncIterator[str],
) -> AsyncIterator[str]:
    """Start a task, dual-write each SSE chunk to EventStore, then close the lifecycle."""
    service.start(task_id)
    try:
        async for chunk in workflow_events:
            event_type, payload = parse_sse_chunk(chunk)
            if event_type:
                service.apply_stream_event(task_id, event_type, payload)
            yield chunk
        service.finish_if_running(task_id)
    except Exception as exc:
        current = service.get(task_id)
        if current.status.value != "cancelled":
            service.mark_failed(task_id, str(exc))
        raise
