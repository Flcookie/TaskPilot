# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Optional

from src.runtime.planning.steps import (
    is_failed,
    is_succeeded,
    needs_execution,
    route_step_type,
)


class AgentLoop:
    """Plan-execute-observe-replan policy. DeepResearch is one implementation."""

    def should_replan(
        self,
        plan: Any,
        *,
        plan_iterations: int = 0,
        max_plan_iterations: int = 1,
    ) -> bool:
        raise NotImplementedError

    def should_finish(
        self,
        plan: Any,
        *,
        plan_iterations: int = 0,
        max_plan_iterations: int = 1,
        has_enough_context: bool | None = None,
    ) -> bool:
        raise NotImplementedError

    def should_interrupt(self, plan: Any, *, auto_accepted_plan: bool = False) -> bool:
        raise NotImplementedError

    def next_executable_step(self, plan: Any) -> Any | None:
        raise NotImplementedError

    def next_action(self, plan: Any) -> str:
        if self.should_replan(plan):
            return "planner"
        step = self.next_executable_step(plan)
        if step is None:
            return "planner"
        return route_step_type(step)


class DeepResearchLoop(AgentLoop):
    def should_replan(
        self,
        plan: Any,
        *,
        plan_iterations: int = 0,
        max_plan_iterations: int = 1,
    ) -> bool:
        steps = getattr(plan, "steps", None) if plan is not None else None
        if not steps:
            return True
        if any(is_failed(step) for step in steps):
            return True
        return all(is_succeeded(step) for step in steps)

    def should_finish(
        self,
        plan: Any,
        *,
        plan_iterations: int = 0,
        max_plan_iterations: int = 1,
        has_enough_context: bool | None = None,
    ) -> bool:
        if plan_iterations >= max_plan_iterations:
            return True
        return bool(has_enough_context)

    def should_interrupt(self, plan: Any, *, auto_accepted_plan: bool = False) -> bool:
        if auto_accepted_plan:
            return False
        steps = getattr(plan, "steps", None) if plan is not None else None
        return bool(steps) and any(needs_execution(step) for step in steps)

    def next_executable_step(self, plan: Any) -> Any | None:
        steps = getattr(plan, "steps", None) if plan is not None else None
        if not steps:
            return None
        for step in steps:
            if needs_execution(step):
                return step
        return None


_loop: Optional[AgentLoop] = None


def get_agent_loop() -> AgentLoop:
    global _loop
    if _loop is None:
        _loop = DeepResearchLoop()
    return _loop


def set_agent_loop(loop: Optional[AgentLoop]) -> None:
    global _loop
    _loop = loop
