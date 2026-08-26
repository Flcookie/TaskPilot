# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from typing import Any, Optional

from pydantic import BaseModel, Field


class ProcessMetrics(BaseModel):
    plan_quality: float = 0.0
    tool_precision: float = 0.0
    recovery_rate: float = 0.0
    token_efficiency: float = 0.0
    loop_stability: float = 0.0
    faithfulness: float = 0.0
    skill_hit_rate: Optional[float] = None
    skill_token_delta: Optional[float] = None
    tool_calls: int = 0
    token_total: int = 0
    latency_ms: Optional[float] = None
    replan_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SkillLoadingArm(BaseModel):
    mode: str
    tokens: int = 0
    skill_count: int = 0
    selected_skills: list[str] = Field(default_factory=list)
    success: Optional[bool] = None
    tool_calls: Optional[int] = None
    latency_ms: Optional[float] = None


class SkillLoadingCompare(BaseModel):
    none: SkillLoadingArm
    all_injected: SkillLoadingArm
    dynamic: SkillLoadingArm
    dynamic_saves_tokens: bool = False
    success_not_worse: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AgentEvaluation(BaseModel):
    process: ProcessMetrics
    process_score: float
    report: Optional[dict[str, Any]] = None
    report_score: Optional[float] = None
    report_grade: Optional[str] = None
    final_score: float
    summary: str
    skill_loading: Optional[SkillLoadingCompare] = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
