# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.runtime.task.service import TaskService, set_task_service
from src.server.app import app


@pytest.fixture
def client():
    set_task_service(TaskService())
    try:
        yield TestClient(app)
    finally:
        set_task_service(None)


def test_create_and_get_task(client):
    created = client.post(
        "/api/tasks",
        json={"messages": [{"role": "user", "content": "Research NI"}], "thread_id": "t-1"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "pending"
    assert body["thread_id"] == "t-1"
    assert body["workflow_type"] == "deep_research"

    fetched = client.get(f"/api/tasks/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_get_missing_task(client):
    response = client.get("/api/tasks/does-not-exist")
    assert response.status_code == 404


def test_resume_pending_task_conflicts(client):
    created = client.post("/api/tasks", json={"messages": []})
    task_id = created.json()["id"]
    response = client.post(f"/api/tasks/{task_id}/resume", json={})
    assert response.status_code == 409


def test_cancel_pending_task(client):
    created = client.post("/api/tasks", json={"messages": []})
    task_id = created.json()["id"]
    response = client.post(f"/api/tasks/{task_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_stream_persists_events_and_succeeds(client):
    created = client.post(
        "/api/tasks",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    task_id = created.json()["id"]

    async def _fake_workflow(*args, **kwargs):
        yield (
            'event: message_chunk\ndata: {"content": "hi", '
            '"langgraph_node": "planner"}\n\n'
        )

    with patch("src.server.app._astream_workflow_generator", _fake_workflow):
        response = client.get(f"/api/tasks/{task_id}/stream")

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "hi" in response.text

    task = client.get(f"/api/tasks/{task_id}").json()
    assert task["status"] == "succeeded"
    assert task["current_node"] == "planner"

    events = client.get(f"/api/tasks/{task_id}/events").json()["events"]
    assert any(event["type"] == "message_chunk" for event in events)
    assert any(event["type"] == "task_started" for event in events)


def test_interrupt_then_resume_and_replay(client):
    created = client.post(
        "/api/tasks",
        json={"messages": [{"role": "user", "content": "plan this"}]},
    )
    task_id = created.json()["id"]

    async def _interrupt_workflow(*args, **kwargs):
        yield (
            'event: interrupt\ndata: {"finish_reason": "interrupt", '
            '"content": "Please Review the Plan."}\n\n'
        )

    with patch("src.server.app._astream_workflow_generator", _interrupt_workflow):
        stream = client.get(f"/api/tasks/{task_id}/stream")

    assert stream.status_code == 200
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "interrupted"

    resumed = client.post(
        f"/api/tasks/{task_id}/resume",
        json={"interrupt_feedback": "accepted"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "pending"

    replay = client.post(f"/api/tasks/{task_id}/replay")
    assert replay.status_code == 200
    assert "interrupt" in replay.text


def test_evaluate_task_returns_process_and_report(client):
    created = client.post(
        "/api/tasks",
        json={"messages": [{"role": "user", "content": "调研量子计算"}]},
    )
    task_id = created.json()["id"]
    from src.runtime.task.service import get_task_service

    service = get_task_service()
    service.append_event(task_id, "skill_loaded", {"allowed_tools": ["web_search"]})
    service.append_event(task_id, "tool_calls", {"name": "web_search"})
    service.append_event(task_id, "token_usage", {"total_tokens": 40})
    service.mark_succeeded(task_id)

    response = client.post(
        f"/api/tasks/{task_id}/evaluate",
        json={
            "report": "# Title\n\n## Key Points\n- a\n\n## Overview\nQuantum.\n",
            "use_llm": False,
            "expected_skill": "deep_research",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "process" in body
    assert body["report_score"] is not None
    assert body["process_score"] > 0
    assert body["skill_loading"]["dynamic_saves_tokens"] is True
