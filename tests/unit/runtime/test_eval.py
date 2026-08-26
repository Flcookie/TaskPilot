# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from src.eval.evaluator import ReportEvaluator
from src.runtime.eval import AgentEvaluator, compare_skill_loading_runs, estimate_skill_loading
from src.runtime.task.models import TaskStatus
from src.runtime.task.service import TaskService, set_task_service


def _seed_task() -> tuple[TaskService, str]:
    service = TaskService()
    task = service.create(
        input_data={"messages": [{"role": "user", "content": "调研英伟达数据中心"}]},
        selected_skills=["deep_research"],
    )
    service.start(task.id)
    service.update_progress(
        task.id,
        plan_snapshot={
            "title": "NVIDIA research",
            "steps": [
                {
                    "need_search": True,
                    "title": "Market size",
                    "description": "Collect datacenter revenue",
                    "step_type": "research",
                }
            ],
        },
    )
    service.append_event(task.id, "skill_loaded", {"allowed_tools": ["web_search", "crawl"]})
    service.append_event(task.id, "tool_calls", {"name": "web_search"})
    service.append_event(task.id, "tool_call_result", {"name": "web_search", "content": "ok"})
    service.append_event(task.id, "token_usage", {"total_tokens": 80})
    service.append_event(
        task.id,
        "message_chunk",
        {
            "langgraph_node": "reporter",
            "content": "# Title\n\n## Key Points\n- a\n\n## Overview\nNVIDIA.\n\n[src](https://nvidianews.nvidia.com/x)\n",
        },
    )
    service.mark_succeeded(task.id)
    return service, task.id


def test_agent_evaluator_returns_process_and_report_scores():
    service, task_id = _seed_task()
    set_task_service(service)
    try:
        import asyncio

        result = asyncio.run(
            AgentEvaluator(tasks=service, reports=ReportEvaluator(use_llm=False)).evaluate(
                task_id,
                expected_skill="deep_research",
            )
        )
        assert result.report_score is not None
        assert result.process_score > 0
        assert result.final_score > 0
        assert result.process.tool_calls >= 1
        assert result.process.token_total == 80
        assert result.process.skill_hit_rate == 1.0
        assert result.process.recovery_rate == 1.0
        assert result.skill_loading is not None
        assert result.skill_loading.dynamic_saves_tokens is True
        assert "Process score" in result.summary
        assert "Report score" in result.summary
    finally:
        set_task_service(None)


def test_failed_tool_then_success_has_recovery():
    service = TaskService()
    task = service.create()
    service.append_event(task.id, "tool_calls", {"name": "web_search"})
    service.append_event(task.id, "tool_call_result", {"name": "web_search", "content": "[ERROR] timeout"})
    service.append_event(task.id, "tool_calls", {"name": "crawl"})
    service.append_event(task.id, "tool_call_result", {"name": "crawl", "content": "ok"})
    service.mark_succeeded(task.id)
    metrics = AgentEvaluator(tasks=service).score_process(service.get(task.id), service.list_events(task.id))
    assert metrics.recovery_rate == 1.0
    assert metrics.tool_precision < 1.0 or metrics.tool_calls >= 2


def test_skill_loading_dynamic_uses_fewer_tokens_than_all_injected():
    compare = estimate_skill_loading("调研量子计算")
    assert compare.none.tokens == 0
    assert compare.all_injected.tokens > compare.dynamic.tokens
    assert compare.dynamic.skill_count == 1
    assert compare.dynamic_saves_tokens is True
    assert "deep_research" in compare.dynamic.selected_skills


def test_skill_loading_run_compare_keeps_success():
    service = TaskService()
    dynamic = service.create()
    service.append_event(dynamic.id, "token_usage", {"total_tokens": 40})
    service.mark_succeeded(dynamic.id)
    all_injected = service.create()
    service.append_event(all_injected.id, "token_usage", {"total_tokens": 120})
    service.mark_succeeded(all_injected.id)
    none = service.create()
    service.append_event(none.id, "token_usage", {"total_tokens": 10})
    service.mark_succeeded(none.id)
    result = compare_skill_loading_runs(
        {
            "dynamic": service.list_events(dynamic.id),
            "all_injected": service.list_events(all_injected.id),
            "no_skill": service.list_events(none.id),
        }
    )
    assert result.dynamic.tokens == 40
    assert result.all_injected.tokens == 120
    assert result.dynamic_saves_tokens is True
    assert result.success_not_worse is True
