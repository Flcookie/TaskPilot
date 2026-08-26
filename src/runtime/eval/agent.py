# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Optional

from src.eval.evaluator import ReportEvaluator
from src.eval.metrics import compute_metrics
from src.runtime.eval.models import AgentEvaluation, ProcessMetrics
from src.runtime.eval.skill_loading import estimate_skill_loading, summarize_events
from src.runtime.skills.apply import extract_user_text
from src.runtime.task.models import Task, TaskEvent, TaskStatus
from src.runtime.task.service import TaskService, get_task_service


class AgentEvaluator:
    """Process metrics from TaskEvent; report quality stays in ReportEvaluator."""

    def __init__(self, tasks: Optional[TaskService] = None, reports: Optional[ReportEvaluator] = None) -> None:
        self._tasks = tasks
        self._reports = reports or ReportEvaluator(use_llm=False)

    @property
    def tasks(self) -> TaskService:
        return self._tasks or get_task_service()

    async def evaluate(
        self,
        task_id: str,
        *,
        report: Optional[str] = None,
        query: Optional[str] = None,
        report_style: str = "default",
        use_llm: bool = False,
        expected_skill: Optional[str] = None,
    ) -> AgentEvaluation:
        task = self.tasks.get(task_id)
        events = self.tasks.list_events(task_id)
        user_text = query or extract_user_text(task.input.get("messages") or [])
        report_text = report or _extract_report(events)
        process = self.score_process(task, events, report_text, expected_skill=expected_skill)
        process_score = _process_score(process)

        report_payload = None
        report_score = None
        report_grade = None
        if report_text:
            self._reports.use_llm = use_llm
            if use_llm:
                combined = await self._reports.evaluate(report_text, user_text or "", report_style)
                report_payload = combined.to_dict()
                report_score = combined.final_score
                report_grade = combined.grade
            else:
                metrics_only = self._reports.evaluate_metrics_only(report_text, report_style)
                report_payload = metrics_only
                report_score = metrics_only["score"]
                report_grade = metrics_only["grade"]

        skill_loading = estimate_skill_loading(user_text) if user_text else None
        if skill_loading is not None:
            process.skill_token_delta = (
                skill_loading.all_injected.tokens - skill_loading.dynamic.tokens
            )

        if report_score is not None:
            final_score = round(process_score * 0.4 + report_score * 0.6, 2)
        else:
            final_score = process_score

        return AgentEvaluation(
            process=process,
            process_score=process_score,
            report=report_payload,
            report_score=report_score,
            report_grade=report_grade,
            final_score=final_score,
            summary=_summary(process, process_score, report_score, report_grade),
            skill_loading=skill_loading,
        )

    def score_process(
        self,
        task: Task,
        events: list[TaskEvent],
        report: Optional[str] = None,
        *,
        expected_skill: Optional[str] = None,
    ) -> ProcessMetrics:
        stats = summarize_events(events)
        allowed = _allowed_tools(events)
        tool_names = _tool_names(events)
        errors = _tool_errors(events)
        replan_count = _replan_count(events, task)
        plan_quality = _plan_quality(task)
        if allowed and tool_names:
            tool_precision = sum(1 for name in tool_names if name in allowed) / len(tool_names)
        elif tool_names:
            ok = max(len(tool_names) - len(errors), 0)
            tool_precision = ok / len(tool_names)
        else:
            tool_precision = 1.0
        if not errors:
            recovery_rate = 1.0
        elif task.status == TaskStatus.SUCCEEDED:
            recovery_rate = 1.0
        elif len(tool_names) > len(errors):
            recovery_rate = 0.7
        else:
            recovery_rate = 0.0
        loop_stability = max(0.0, 1.0 - max(replan_count - 1, 0) * 0.25)
        tokens = stats["tokens"]
        output_chars = len(report or "")
        if tokens <= 0:
            token_efficiency = 0.5 if output_chars else 0.0
        else:
            token_efficiency = min(1.0, output_chars / (tokens * 8))
        faithfulness = _faithfulness(report, events)
        skill_hit = None
        if expected_skill:
            skill_hit = 1.0 if expected_skill in (task.selected_skills or []) else 0.0
        return ProcessMetrics(
            plan_quality=round(plan_quality, 3),
            tool_precision=round(tool_precision, 3),
            recovery_rate=round(recovery_rate, 3),
            token_efficiency=round(token_efficiency, 3),
            loop_stability=round(loop_stability, 3),
            faithfulness=round(faithfulness, 3),
            skill_hit_rate=skill_hit,
            tool_calls=stats["tool_calls"],
            token_total=tokens,
            latency_ms=stats["latency_ms"],
            replan_count=replan_count,
        )


def _process_score(metrics: ProcessMetrics) -> float:
    values = [
        metrics.plan_quality,
        metrics.tool_precision,
        metrics.recovery_rate,
        metrics.token_efficiency,
        metrics.loop_stability,
        metrics.faithfulness,
    ]
    if metrics.skill_hit_rate is not None:
        values.append(metrics.skill_hit_rate)
    return round(sum(values) / len(values) * 10, 2)


def _plan_quality(task: Task) -> float:
    plan = task.plan_snapshot or {}
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not steps:
        return 0.4 if task.status == TaskStatus.SUCCEEDED else 0.2
    score = 0.4
    if 1 <= len(steps) <= 8:
        score += 0.2
    complete = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("title") and step.get("description") and step.get("step_type"):
            complete += 1
    score += 0.4 * (complete / len(steps))
    return min(score, 1.0)


def _allowed_tools(events: list[TaskEvent]) -> set[str]:
    allowed: set[str] = set()
    for event in events:
        if event.type != "skill_loaded":
            continue
        names = event.payload.get("allowed_tools") or []
        allowed.update(str(name) for name in names)
    return allowed


def _tool_names(events: list[TaskEvent]) -> list[str]:
    names: list[str] = []
    for event in events:
        if event.type not in {"tool_calls", "tool_start", "tool_call_result"}:
            continue
        calls = event.payload.get("tool_calls") or event.payload.get("calls") or []
        if isinstance(calls, list):
            for item in calls:
                if isinstance(item, dict) and (item.get("name") or item.get("tool_name")):
                    names.append(str(item.get("name") or item.get("tool_name")))
        name = event.payload.get("name") or event.payload.get("tool_name")
        if name:
            names.append(str(name))
    return names


def _tool_errors(events: list[TaskEvent]) -> list[TaskEvent]:
    found = []
    for event in events:
        if event.type in {"tool_error", "error"}:
            found.append(event)
            continue
        if event.type != "tool_call_result":
            continue
        payload = event.payload
        content = str(payload.get("content") or payload.get("error") or "")
        if payload.get("ok") is False or "error" in content.lower() or "[error]" in content.lower():
            found.append(event)
    return found


def _replan_count(events: list[TaskEvent], task: Task) -> int:
    planner = 0
    for event in events:
        node = event.payload.get("langgraph_node") or event.payload.get("agent") or event.payload.get("node")
        if event.type == "plan_update" or node == "planner":
            planner += 1
    if planner:
        return max(planner - 1, 0)
    return 0


def _faithfulness(report: Optional[str], events: list[TaskEvent]) -> float:
    citation_events = [event for event in events if event.type == "citations"]
    if report:
        metrics = compute_metrics(report)
        if metrics.citation_count:
            return min(1.0, 0.4 + metrics.citation_count / 10)
        if metrics.has_citations_section:
            return 0.6
        return 0.3
    if citation_events:
        return 0.6
    return 0.2


def _extract_report(events: list[TaskEvent]) -> str:
    chunks: list[str] = []
    for event in events:
        node = event.payload.get("langgraph_node") or event.payload.get("agent")
        if event.type == "message_chunk" and node == "reporter":
            content = event.payload.get("content")
            if isinstance(content, str):
                chunks.append(content)
    return "".join(chunks)


def _summary(
    process: ProcessMetrics,
    process_score: float,
    report_score: Optional[float],
    report_grade: Optional[str],
) -> str:
    lines = [f"Process score: {process_score}/10"]
    if report_score is not None:
        lines.append(f"Report score: {report_score}/10 ({report_grade})")
    lines.append(f"- tool_calls={process.tool_calls} tokens={process.token_total} replans={process.replan_count}")
    lines.append(
        f"- precision={process.tool_precision} recovery={process.recovery_rate} "
        f"stability={process.loop_stability}"
    )
    return "\n".join(lines)
