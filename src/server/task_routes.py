# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from src.config.loader import get_bool_env
from src.runtime.task.models import STARTABLE_STATUSES
from src.runtime.task.service import (
    TaskConflictError,
    TaskNotFoundError,
    get_task_service,
)
from src.runtime.task.sse import persist_workflow_stream, replay_events_as_sse
from src.server.task_request import (
    CreateTaskRequest,
    ResumeTaskRequest,
    TaskEventListResponse,
    TaskEventResponse,
    TaskResponse,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_or_404(task_id: str):
    try:
        return get_task_service().get(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _raise_conflict(exc: TaskConflictError) -> None:
    raise HTTPException(status_code=409, detail=str(exc)) from exc


def _split_create_payload(request: CreateTaskRequest) -> tuple[str, dict, dict]:
    payload = request.model_dump()
    workflow_type = payload.pop("workflow_type", "deep_research") or "deep_research"
    thread_id = payload.pop("thread_id", None)
    if not thread_id or thread_id == "__default__":
        thread_id = str(uuid4())
    input_data = {"messages": payload.pop("messages", []) or []}
    return thread_id, input_data, payload | {"workflow_type": workflow_type}


@router.post("", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):
    mcp_enabled = get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False)
    if request.mcp_settings and not mcp_enabled:
        raise HTTPException(
            status_code=403,
            detail=(
                "MCP server configuration is disabled. "
                "Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features."
            ),
        )

    thread_id, input_data, config = _split_create_payload(request)
    task = get_task_service().create(
        thread_id=thread_id,
        input_data=input_data,
        config=config,
        workflow_type=config.get("workflow_type", "deep_research"),
    )
    return TaskResponse.from_task(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    return TaskResponse.from_task(_task_or_404(task_id))


@router.get("/{task_id}/events", response_model=TaskEventListResponse)
async def list_task_events(task_id: str, after_seq: int = 0):
    _task_or_404(task_id)
    events = get_task_service().list_events(task_id, after_seq=after_seq)
    return TaskEventListResponse(
        task_id=task_id,
        events=[TaskEventResponse.from_event(event) for event in events],
    )


@router.get("/{task_id}/stream")
async def stream_task(
    task_id: str,
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
):
    task = _task_or_404(task_id)
    after_seq = 0
    if last_event_id:
        try:
            after_seq = int(last_event_id)
        except ValueError:
            after_seq = 0

    if after_seq <= 0 and task.status not in STARTABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} cannot start from status={task.status.value}",
        )

    return StreamingResponse(
        _stream_task_events(task_id, after_seq),
        media_type="text/event-stream",
    )


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str):
    _task_or_404(task_id)
    try:
        task = get_task_service().cancel(task_id)
    except TaskConflictError as exc:
        _raise_conflict(exc)
    return TaskResponse.from_task(task)


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(task_id: str, request: ResumeTaskRequest | None = None):
    _task_or_404(task_id)
    feedback = request.interrupt_feedback if request else None
    try:
        task = get_task_service().resume(task_id, interrupt_feedback=feedback)
    except TaskConflictError as exc:
        _raise_conflict(exc)
    return TaskResponse.from_task(task)


@router.post("/{task_id}/replay")
async def replay_task(task_id: str):
    _task_or_404(task_id)
    events = get_task_service().list_events(task_id)

    async def _replay():
        for chunk in replay_events_as_sse(events):
            yield chunk

    return StreamingResponse(_replay(), media_type="text/event-stream")


async def _stream_task_events(task_id: str, after_seq: int = 0):
    from src.server.app import _astream_workflow_generator
    from src.server.chat_request import ChatRequest

    service = get_task_service()
    task = service.get(task_id)
    if after_seq > 0:
        for chunk in replay_events_as_sse(service.list_events(task_id, after_seq=after_seq)):
            yield chunk

    chat_request = ChatRequest.model_validate(
        {
            **task.config,
            "messages": task.input.get("messages", []),
            "thread_id": task.thread_id,
        }
    )
    workflow = _astream_workflow_generator(
        chat_request.model_dump()["messages"],
        task.thread_id,
        chat_request.resources,
        chat_request.max_plan_iterations,
        chat_request.max_step_num,
        chat_request.max_search_results,
        chat_request.auto_accepted_plan,
        chat_request.interrupt_feedback,
        chat_request.mcp_settings or {},
        chat_request.enable_background_investigation,
        chat_request.enable_web_search,
        chat_request.report_style,
        chat_request.enable_deep_thinking,
        chat_request.enable_clarification,
        chat_request.max_clarification_rounds,
        chat_request.locale,
        chat_request.interrupt_before_tools,
        task_id,
    )
    async for chunk in persist_workflow_stream(service, task_id, workflow):
        yield chunk
