# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.server.chat_request import ChatRequest
from src.runtime.task.models import Task, TaskEvent, TaskStatus


class CreateTaskRequest(ChatRequest):
    workflow_type: Optional[str] = Field(
        "deep_research", description="Workflow implementation to run"
    )


class ResumeTaskRequest(BaseModel):
    interrupt_feedback: Optional[str] = Field(
        None, description="Feedback used when resuming from an interrupt"
    )


class EvaluateTaskRequest(BaseModel):
    report: Optional[str] = Field(None, description="Report markdown; inferred from reporter events if omitted")
    query: Optional[str] = Field(None, description="Original user query")
    report_style: Optional[str] = Field("default")
    use_llm: bool = Field(False, description="Also run ReportEvaluator LLM-as-Judge")
    expected_skill: Optional[str] = Field(None, description="Label for skill_hit_rate")


class TaskResponse(BaseModel):
    id: str
    status: TaskStatus
    workflow_type: str
    thread_id: str
    selected_skills: list[str] = Field(default_factory=list)
    current_node: Optional[str] = None
    current_step_index: Optional[int] = None
    plan_snapshot: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @classmethod
    def from_task(cls, task: Task) -> "TaskResponse":
        return cls(
            id=task.id,
            status=task.status,
            workflow_type=task.workflow_type,
            thread_id=task.thread_id,
            selected_skills=task.selected_skills,
            current_node=task.current_node,
            current_step_index=task.current_step_index,
            plan_snapshot=task.plan_snapshot,
            error=task.error,
            created_at=task.created_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )


class TaskEventResponse(BaseModel):
    task_id: str
    seq: int
    ts: datetime
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_event(cls, event: TaskEvent) -> "TaskEventResponse":
        return cls(
            task_id=event.task_id,
            seq=event.seq,
            ts=event.ts,
            type=event.type,
            payload=event.payload,
        )


class TaskEventListResponse(BaseModel):
    task_id: str
    events: list[TaskEventResponse]
