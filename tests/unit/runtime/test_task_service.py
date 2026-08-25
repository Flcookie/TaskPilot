# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

import pytest

from src.runtime.task.models import TaskStatus
from src.runtime.task.service import TaskConflictError, TaskNotFoundError, TaskService
from src.runtime.task.sse import parse_sse_chunk, persist_workflow_stream


def test_create_task_starts_pending():
    service = TaskService()
    task = service.create(input_data={"messages": []}, thread_id="thread-1")
    assert task.status == TaskStatus.PENDING
    assert task.thread_id == "thread-1"
    assert service.list_events(task.id)[0].type == "task_created"


def test_get_missing_task_raises():
    service = TaskService()
    with pytest.raises(TaskNotFoundError):
        service.get("missing")


def test_resume_pending_conflicts():
    service = TaskService()
    task = service.create()
    with pytest.raises(TaskConflictError):
        service.resume(task.id)


def test_resume_from_interrupted_returns_pending():
    service = TaskService()
    task = service.create()
    service.start(task.id)
    service.mark_interrupted(task.id)
    resumed = service.resume(task.id, interrupt_feedback="accepted")
    assert resumed.status == TaskStatus.PENDING
    assert resumed.config["interrupt_feedback"] == "accepted"


def test_cancel_succeeded_conflicts():
    service = TaskService()
    task = service.create()
    service.start(task.id)
    service.mark_succeeded(task.id)
    with pytest.raises(TaskConflictError):
        service.cancel(task.id)


def test_apply_stream_event_projects_node_and_interrupt():
    service = TaskService()
    task = service.create()
    service.start(task.id)
    service.apply_stream_event(
        task.id,
        "message_chunk",
        {"content": "hi", "langgraph_node": "planner"},
    )
    interrupted = service.apply_stream_event(
        task.id,
        "interrupt",
        {"finish_reason": "interrupt"},
    )
    assert interrupted.current_node == "planner"
    assert interrupted.status == TaskStatus.INTERRUPTED


def test_finish_if_running_marks_succeeded():
    service = TaskService()
    task = service.create()
    service.start(task.id)
    finished = service.finish_if_running(task.id)
    assert finished.status == TaskStatus.SUCCEEDED


def test_parse_sse_chunk():
    event_type, payload = parse_sse_chunk(
        'event: message_chunk\ndata: {"content": "hello"}\n\n'
    )
    assert event_type == "message_chunk"
    assert payload["content"] == "hello"


@pytest.mark.asyncio
async def test_persist_workflow_stream_writes_events():
    service = TaskService()
    task = service.create()

    async def _fake_workflow():
        yield 'event: message_chunk\ndata: {"content": "hi", "langgraph_node": "reporter"}\n\n'

    chunks = []
    async for chunk in persist_workflow_stream(service, task.id, _fake_workflow()):
        chunks.append(chunk)

    stored = service.get(task.id)
    assert stored.status == TaskStatus.SUCCEEDED
    assert stored.current_node == "reporter"
    types = [event.type for event in service.list_events(task.id)]
    assert "message_chunk" in types
    assert chunks[0].startswith("event: message_chunk")
