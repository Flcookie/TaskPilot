# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from src.prompts.planner_model import Plan, Step
from src.runtime.planning.steps import (
    as_pending_step,
    effective_status,
    is_failed,
    is_succeeded,
    step_key,
)


RESULT_PREVIEW = 400


def format_plan_progress(plan: Any) -> str:
    """Planner input: completed / failed / pending steps."""
    steps = getattr(plan, "steps", None) if plan is not None else None
    if not steps:
        return ""

    succeeded: list[str] = []
    failed: list[str] = []
    pending: list[str] = []
    for index, step in enumerate(steps, start=1):
        title = getattr(step, "title", None) or f"Step {index}"
        status = effective_status(step).value
        result = str(getattr(step, "execution_res", "") or "").strip()
        preview = result[:RESULT_PREVIEW]
        line = f"{index}. [{status}] {title}"
        if preview:
            line = f"{line}\n   result: {preview}"
        if is_succeeded(step):
            succeeded.append(line)
        elif is_failed(step):
            failed.append(line)
        else:
            pending.append(line)

    sections = [
        "# Current Plan Progress",
        "Keep every succeeded step unchanged. Only rewrite failed or pending steps.",
        "Do not ask the runtime to rerun succeeded steps.",
    ]
    sections.append("## Succeeded steps")
    sections.extend(succeeded or ["- none"])
    sections.append("## Failed steps")
    sections.extend(failed or ["- none"])
    sections.append("## Pending / running steps")
    sections.extend(pending or ["- none"])
    return "\n".join(sections)


def apply_plan_diff(current: Plan | None, proposed: Plan | dict) -> Plan:
    """Keep succeeded steps; replace only failed / pending / new work."""
    incoming = proposed if isinstance(proposed, Plan) else Plan.model_validate(proposed)
    if current is None or not getattr(current, "steps", None):
        return incoming

    succeeded = [step for step in current.steps if is_succeeded(step)]
    succeeded_keys = {step_key(step) for step in succeeded if step_key(step)}
    failed = [step for step in current.steps if is_failed(step)]

    replacements: list[Step] = []
    for step in incoming.steps:
        key = step_key(step)
        if key and key in succeeded_keys:
            continue
        replacements.append(as_pending_step(step))

    if not replacements and failed:
        replacements = [as_pending_step(step) for step in failed]

    return incoming.model_copy(update={"steps": [*succeeded, *replacements]})
