# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from src.prompts.planner_model import Step, StepStatus, StepType

TERMINAL_STATUSES = {StepStatus.SUCCEEDED, StepStatus.SKIPPED, StepStatus.FAILED}
SUCCESS_STATUSES = {StepStatus.SUCCEEDED, StepStatus.SKIPPED}


def effective_status(step: Any) -> StepStatus:
    raw = getattr(step, "status", None)
    if raw:
        try:
            return StepStatus(raw)
        except ValueError:
            pass
    if getattr(step, "execution_res", None):
        return StepStatus.SUCCEEDED
    return StepStatus.PENDING


def needs_execution(step: Any) -> bool:
    return effective_status(step) in {StepStatus.PENDING, StepStatus.RUNNING}


def is_succeeded(step: Any) -> bool:
    return effective_status(step) in SUCCESS_STATUSES


def is_failed(step: Any) -> bool:
    return effective_status(step) == StepStatus.FAILED


def step_key(step: Any) -> str:
    title = str(getattr(step, "title", "") or "").strip().lower()
    if title:
        return title
    return str(getattr(step, "description", "") or "")[:80].strip().lower()


def mark_step(step: Any, status: StepStatus, execution_res: str | None = None) -> Any:
    if hasattr(step, "status"):
        step.status = status
    if execution_res is not None and hasattr(step, "execution_res"):
        step.execution_res = execution_res
    return step


def as_pending_step(step: Any) -> Step:
    if isinstance(step, Step):
        return step.model_copy(
            update={"status": StepStatus.PENDING, "execution_res": None}
        )
    data = step if isinstance(step, dict) else {}
    if not data and hasattr(step, "model_dump"):
        data = step.model_dump()
    elif not data:
        data = {
            "need_search": bool(getattr(step, "need_search", False)),
            "title": getattr(step, "title", "Untitled"),
            "description": getattr(step, "description", ""),
            "step_type": getattr(step, "step_type", StepType.RESEARCH),
        }
    data = {**data, "status": StepStatus.PENDING, "execution_res": None}
    return Step.model_validate(data)


def route_step_type(step: Any) -> str:
    step_type = getattr(step, "step_type", None)
    if step_type == StepType.RESEARCH or step_type == "research":
        return "researcher"
    if step_type == StepType.ANALYSIS or step_type == "analysis":
        return "analyst"
    if step_type == StepType.PROCESSING or step_type == "processing":
        return "coder"
    return "planner"
