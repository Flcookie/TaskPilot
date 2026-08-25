# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


RESUMABLE_STATUSES = frozenset({TaskStatus.INTERRUPTED, TaskStatus.FAILED})
CANCELLABLE_STATUSES = frozenset(
    {TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.INTERRUPTED}
)
STARTABLE_STATUSES = frozenset(
    {TaskStatus.PENDING, TaskStatus.INTERRUPTED, TaskStatus.FAILED}
)
TERMINAL_STATUSES = frozenset(
    {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
)


class Task(BaseModel):
    id: str
    user_id: Optional[str] = None
    workflow_type: str = "deep_research"
    status: TaskStatus = TaskStatus.PENDING
    input: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    selected_skills: list[str] = Field(default_factory=list)
    current_node: Optional[str] = None
    current_step_index: Optional[int] = None
    plan_snapshot: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    thread_id: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TaskEvent(BaseModel):
    task_id: str
    seq: int
    ts: datetime
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
