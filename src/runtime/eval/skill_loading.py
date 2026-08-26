# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Optional

from src.runtime.eval.models import SkillLoadingArm, SkillLoadingCompare
from src.runtime.skills.loader import get_skill_loader
from src.runtime.skills.registry import get_skill_registry
from src.runtime.skills.router import heuristic_select
from src.runtime.task.models import TaskEvent


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_skill_loading(user_text: str) -> SkillLoadingCompare:
    """Token cost of No Skill vs All Injected vs Dynamic Loading."""
    registry = get_skill_registry()
    loader = get_skill_loader()
    metas = registry.all()
    all_bodies = [loader.load(meta.name).body for meta in metas]
    all_tokens = sum(estimate_tokens(body) for body in all_bodies)
    selected = heuristic_select(user_text, metas).name

    dynamic_body = loader.load(selected).body if selected and registry.get(selected) else ""
    dynamic_tokens = estimate_tokens(dynamic_body)
    selected_skills = [selected] if selected else []

    return SkillLoadingCompare(
        none=SkillLoadingArm(mode="no_skill", tokens=0, skill_count=0),
        all_injected=SkillLoadingArm(
            mode="all_injected",
            tokens=all_tokens,
            skill_count=len(all_bodies),
            selected_skills=[meta.name for meta in metas],
        ),
        dynamic=SkillLoadingArm(
            mode="dynamic",
            tokens=dynamic_tokens,
            skill_count=1 if selected_skills else 0,
            selected_skills=selected_skills,
        ),
        dynamic_saves_tokens=dynamic_tokens < all_tokens,
    )


def summarize_events(events: list[TaskEvent]) -> dict[str, Any]:
    tokens = 0
    tool_calls = 0
    succeeded = False
    for event in events:
        if event.type == "token_usage":
            tokens += int(event.payload.get("total_tokens") or 0)
        if event.type in {"tool_calls", "tool_start"}:
            tool_calls += _tool_call_count(event.payload)
        if event.type == "status" and event.payload.get("status") == "succeeded":
            succeeded = True
    latency_ms = None
    if events:
        latency_ms = (events[-1].ts - events[0].ts).total_seconds() * 1000
    return {
        "success": succeeded,
        "tokens": tokens,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
    }


def compare_skill_loading_runs(
    runs: dict[str, list[TaskEvent]],
    *,
    prompt_estimate: Optional[SkillLoadingCompare] = None,
) -> SkillLoadingCompare:
    """Compare recorded runs. Prompt token estimate still comes from skill bodies."""
    base = prompt_estimate or SkillLoadingCompare(
        none=SkillLoadingArm(mode="no_skill"),
        all_injected=SkillLoadingArm(mode="all_injected"),
        dynamic=SkillLoadingArm(mode="dynamic"),
        dynamic_saves_tokens=False,
    )
    mapped = {
        "no_skill": base.none,
        "none": base.none,
        "all_injected": base.all_injected,
        "all": base.all_injected,
        "dynamic": base.dynamic,
    }
    for key, events in runs.items():
        arm = mapped.get(key)
        if arm is None:
            continue
        stats = summarize_events(events)
        arm.success = stats["success"]
        arm.tool_calls = stats["tool_calls"]
        arm.latency_ms = stats["latency_ms"]
        if stats["tokens"]:
            arm.tokens = stats["tokens"]
    successes = [arm.success for arm in (base.none, base.all_injected, base.dynamic) if arm.success is not None]
    all_ok = base.all_injected.success
    dynamic_ok = base.dynamic.success
    success_not_worse = None
    if all_ok is not None and dynamic_ok is not None:
        success_not_worse = bool(dynamic_ok) or not bool(all_ok)
    elif successes:
        success_not_worse = True
    return SkillLoadingCompare(
        none=base.none,
        all_injected=base.all_injected,
        dynamic=base.dynamic,
        dynamic_saves_tokens=base.dynamic.tokens < base.all_injected.tokens,
        success_not_worse=success_not_worse,
    )


def _tool_call_count(payload: dict[str, Any]) -> int:
    calls = payload.get("tool_calls") or payload.get("calls")
    if isinstance(calls, list) and calls:
        return len(calls)
    if payload.get("name") or payload.get("tool_name"):
        return 1
    return 0
