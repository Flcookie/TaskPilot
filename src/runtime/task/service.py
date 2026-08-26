# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from src.runtime.task.models import (
    CANCELLABLE_STATUSES,
    RESUMABLE_STATUSES,
    STARTABLE_STATUSES,
    Task,
    TaskEvent,
    TaskStatus,
    utc_now,
)
from src.runtime.task.store import InMemoryTaskStore, TaskStore, create_task_store


class TaskConflictError(Exception):
    def __init__(self, message: str, task: Optional[Task] = None) -> None:
        super().__init__(message)
        self.task = task


class TaskNotFoundError(Exception):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class TaskService:
    def __init__(self, store: Optional[TaskStore] = None) -> None:
        self._store = store or InMemoryTaskStore()

    def create(
        self,
        *,
        thread_id: Optional[str] = None,
        input_data: Optional[dict[str, Any]] = None,
        config: Optional[dict[str, Any]] = None,
        workflow_type: str = "deep_research",
        user_id: Optional[str] = None,
        selected_skills: Optional[list[str]] = None,
    ) -> Task:
        now = utc_now()
        task = Task(
            id=str(uuid4()),
            user_id=user_id,
            workflow_type=workflow_type,
            status=TaskStatus.PENDING,
            input=input_data or {},
            config=config or {},
            selected_skills=selected_skills or [],
            thread_id=thread_id or str(uuid4()),
            created_at=now,
        )
        saved = self._store.put_task(task)
        self.append_event(saved.id, "task_created", {"status": saved.status.value})
        return saved

    def get(self, task_id: str) -> Task:
        task = self._store.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def list_events(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
        self.get(task_id)
        return self._store.list_events(task_id, after_seq=after_seq)

    def append_event(
        self, task_id: str, event_type: str, payload: Optional[dict[str, Any]] = None
    ) -> TaskEvent:
        task = self.get(task_id)
        event = TaskEvent(
            task_id=task.id,
            seq=self._store.next_seq(task.id),
            ts=utc_now(),
            type=event_type,
            payload=payload or {},
        )
        return self._store.append_event(event)

    def start(self, task_id: str) -> Task:
        task = self.get(task_id)
        if task.status not in STARTABLE_STATUSES:
            raise TaskConflictError(
                f"Task {task_id} cannot start from status={task.status.value}",
                task,
            )
        now = utc_now()
        task.status = TaskStatus.RUNNING
        task.started_at = task.started_at or now
        task.finished_at = None
        task.error = None
        saved = self._store.put_task(task)
        self.append_event(saved.id, "task_started", {"status": saved.status.value})
        return saved

    def cancel(self, task_id: str) -> Task:
        task = self.get(task_id)
        if task.status not in CANCELLABLE_STATUSES:
            raise TaskConflictError(
                f"Task {task_id} cannot cancel from status={task.status.value}",
                task,
            )
        task.status = TaskStatus.CANCELLED
        task.finished_at = utc_now()
        saved = self._store.put_task(task)
        self.append_event(saved.id, "task_cancelled", {"status": saved.status.value})
        return saved

    def resume(self, task_id: str, interrupt_feedback: Optional[str] = None) -> Task:
        task = self.get(task_id)
        if task.status not in RESUMABLE_STATUSES:
            raise TaskConflictError(
                f"Task {task_id} cannot resume from status={task.status.value}",
                task,
            )
        if interrupt_feedback is not None:
            task.config = {**task.config, "interrupt_feedback": interrupt_feedback}
        task.status = TaskStatus.PENDING
        task.error = None
        task.finished_at = None
        saved = self._store.put_task(task)
        self.append_event(
            saved.id,
            "task_resumed",
            {"status": saved.status.value, "from": "resumable"},
        )
        return saved

    def mark_interrupted(self, task_id: str) -> Task:
        return self._set_status(task_id, TaskStatus.INTERRUPTED, finished=False)

    def mark_succeeded(self, task_id: str) -> Task:
        return self._set_status(task_id, TaskStatus.SUCCEEDED, finished=True)

    def mark_failed(self, task_id: str, error: str) -> Task:
        return self._set_status(
            task_id, TaskStatus.FAILED, finished=True, error=error
        )

    def mark_cancelled(self, task_id: str) -> Task:
        return self._set_status(task_id, TaskStatus.CANCELLED, finished=True)

    def update_progress(
        self,
        task_id: str,
        *,
        current_node: Optional[str] = None,
        current_step_index: Optional[int] = None,
        plan_snapshot: Optional[dict[str, Any]] = None,
    ) -> Task:
        task = self.get(task_id)
        if current_node is not None:
            task.current_node = current_node
        if current_step_index is not None:
            task.current_step_index = current_step_index
        if plan_snapshot is not None:
            task.plan_snapshot = plan_snapshot
        return self._store.put_task(task)

    def apply_stream_event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> Task:
        """Persist one SSE event and project status / progress onto the Task."""
        self.append_event(task_id, event_type, payload)

        node = payload.get("langgraph_node") or payload.get("agent")
        if isinstance(node, str) and node:
            self.update_progress(task_id, current_node=node)

        plan = payload.get("current_plan") or payload.get("plan_snapshot")
        if isinstance(plan, dict):
            self.update_progress(task_id, plan_snapshot=plan)

        task = self.get(task_id)
        if event_type == "interrupt" or payload.get("finish_reason") == "interrupt":
            return self.mark_interrupted(task_id)
        if event_type == "error":
            if payload.get("reason") == "cancelled":
                return self.mark_cancelled(task_id)
            return self.mark_failed(
                task_id, str(payload.get("error") or "Error during graph execution")
            )
        return task

    def finish_if_running(self, task_id: str) -> Task:
        task = self.get(task_id)
        if task.status == TaskStatus.RUNNING:
            return self.mark_succeeded(task_id)
        return task

    def _set_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        finished: bool,
        error: Optional[str] = None,
    ) -> Task:
        task = self.get(task_id)
        if task.status == status:
            return task
        if task.status == TaskStatus.CANCELLED and status != TaskStatus.CANCELLED:
            return task
        task.status = status
        if error is not None:
            task.error = error
        if finished:
            task.finished_at = utc_now()
        else:
            task.finished_at = None
        saved = self._store.put_task(task)
        self.append_event(
            saved.id,
            "status",
            {"status": saved.status.value, "error": saved.error},
        )
        return saved


_service: Optional[TaskService] = None


def get_task_service() -> TaskService:
    global _service
    if _service is None:
        _service = TaskService(store=create_task_store())
    return _service


def set_task_service(service: Optional[TaskService]) -> None:
    global _service
    _service = service
