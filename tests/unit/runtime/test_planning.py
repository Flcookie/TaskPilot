# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from src.graph.builder import continue_to_running_research_team
from src.prompts.planner_model import Plan, Step, StepStatus, StepType
from src.runtime.planning import (
    DeepResearchLoop,
    apply_plan_diff,
    format_plan_progress,
    get_agent_loop,
)


def _step(
    title: str,
    *,
    status: StepStatus = StepStatus.PENDING,
    execution_res: str | None = None,
    step_type: StepType = StepType.RESEARCH,
) -> Step:
    return Step(
        need_search=step_type == StepType.RESEARCH,
        title=title,
        description=f"Do {title}",
        step_type=step_type,
        status=status,
        execution_res=execution_res,
    )


def _plan(*steps: Step) -> Plan:
    return Plan(
        locale="en-US",
        has_enough_context=False,
        thought="draft",
        title="Market research",
        steps=list(steps),
    )


def test_failed_search_only_rewrites_affected_steps():
    current = _plan(
        _step("Company overview", status=StepStatus.SUCCEEDED, execution_res="NVIDIA sells GPUs"),
        _step("Datacenter search", status=StepStatus.FAILED, execution_res="[ERROR] search timeout"),
        _step("Synthesize findings", status=StepStatus.PENDING, step_type=StepType.ANALYSIS),
    )
    proposed = _plan(
        _step("Company overview", status=StepStatus.PENDING),
        _step("Retry datacenter filings"),
        _step("Synthesize findings", step_type=StepType.ANALYSIS),
    )

    merged = apply_plan_diff(current, proposed)

    assert [step.title for step in merged.steps] == [
        "Company overview",
        "Retry datacenter filings",
        "Synthesize findings",
    ]
    overview = merged.steps[0]
    assert overview.status == StepStatus.SUCCEEDED
    assert overview.execution_res == "NVIDIA sells GPUs"
    assert merged.steps[1].status == StepStatus.PENDING
    assert merged.steps[1].execution_res is None
    assert merged.steps[2].status == StepStatus.PENDING


def test_plan_progress_lists_completed_and_failed_steps():
    text = format_plan_progress(
        _plan(
            _step("Company overview", status=StepStatus.SUCCEEDED, execution_res="ok"),
            _step("Datacenter search", status=StepStatus.FAILED, execution_res="timeout"),
        )
    )
    assert "Succeeded steps" in text
    assert "Company overview" in text
    assert "Failed steps" in text
    assert "Datacenter search" in text
    assert "timeout" in text


def test_agent_loop_replans_on_failed_step_without_rerunning_success():
    loop = DeepResearchLoop()
    plan = _plan(
        _step("Company overview", status=StepStatus.SUCCEEDED, execution_res="ok"),
        _step("Datacenter search", status=StepStatus.FAILED, execution_res="timeout"),
        _step("Follow-up", status=StepStatus.PENDING),
    )
    assert loop.should_replan(plan) is True
    assert loop.next_executable_step(plan) is None or loop.next_action(plan) == "planner"
    assert continue_to_running_research_team({"current_plan": plan}) == "planner"


def test_agent_loop_runs_next_pending_research_step():
    loop = get_agent_loop()
    plan = _plan(
        _step("Company overview", status=StepStatus.SUCCEEDED, execution_res="ok"),
        _step("Datacenter search", status=StepStatus.PENDING),
    )
    assert loop.should_replan(plan) is False
    assert loop.next_executable_step(plan).title == "Datacenter search"
    assert continue_to_running_research_team({"current_plan": plan}) == "researcher"


def test_agent_loop_finish_and_interrupt_policy():
    loop = DeepResearchLoop()
    pending = _plan(_step("Search more"))
    assert loop.should_finish(pending, plan_iterations=1, max_plan_iterations=1) is True
    assert loop.should_finish(pending, plan_iterations=0, max_plan_iterations=2) is False
    assert loop.should_finish(pending, has_enough_context=True) is True
    assert loop.should_interrupt(pending, auto_accepted_plan=False) is True
    assert loop.should_interrupt(pending, auto_accepted_plan=True) is False
