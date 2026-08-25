# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from typing import Callable, Optional

from src.runtime.skills.models import SkillChoice, SkillMeta
from src.runtime.skills.registry import SkillRegistry, get_skill_registry

logger = logging.getLogger(__name__)

DEFAULT_SKILL = "deep_research"
Selector = Callable[[str, list[SkillMeta]], SkillChoice]


class SkillRouter:
    def __init__(
        self,
        registry: SkillRegistry | None = None,
        selector: Optional[Selector] = None,
        fallback: str = DEFAULT_SKILL,
    ) -> None:
        self._registry = registry
        self._selector = selector
        self._fallback = fallback

    @property
    def registry(self) -> SkillRegistry:
        return self._registry or get_skill_registry()

    def select(self, user_text: str) -> SkillChoice:
        metas = self.registry.all()
        if not metas:
            return SkillChoice(selected_skills=[self._fallback], reason="empty registry")

        try:
            choice = (self._selector or llm_select)(user_text, metas)
        except Exception as exc:
            logger.warning("Skill router LLM failed, using heuristic: %s", exc)
            choice = heuristic_select(user_text, metas)

        name = choice.name
        if name not in {meta.name for meta in metas}:
            fallback = (
                self._fallback
                if self.registry.get(self._fallback)
                else metas[0].name
            )
            return SkillChoice(
                selected_skills=[fallback],
                reason=choice.reason or f"unknown skill '{name}', fallback to {fallback}",
            )
        return SkillChoice(selected_skills=[name], reason=choice.reason)


def heuristic_select(user_text: str, metas: list[SkillMeta]) -> SkillChoice:
    text = (user_text or "").lower()
    available = {meta.name for meta in metas}

    data_hits = ("计算", "统计", "财报", "季度", "图表", "python", "dataframe", "csv")
    write_hits = ("润色", "改写", "成文", "写一篇", "write a report", "polish")
    if any(token in text for token in data_hits) and "data_analysis" in available:
        if not any(token in text for token in ("调研", "研究", "research", "信源")):
            return SkillChoice(
                selected_skills=["data_analysis"],
                reason="task is primarily numerical analysis",
            )
    if any(token in text for token in write_hits) and "report_writing" in available:
        if not any(token in text for token in ("调研", "搜索", "research")):
            return SkillChoice(
                selected_skills=["report_writing"],
                reason="task is writing from existing material",
            )
    if "deep_research" in available:
        return SkillChoice(
            selected_skills=["deep_research"],
            reason="default complex research workflow",
        )
    return SkillChoice(selected_skills=[metas[0].name], reason="first registered skill")


def llm_select(user_text: str, metas: list[SkillMeta]) -> SkillChoice:
    from src.llms.llm import get_llm_by_type

    catalog = "\n".join(
        f"- {meta.name}: {meta.description} tags={meta.tags}" for meta in metas
    )
    llm = get_llm_by_type("basic")
    if not hasattr(llm, "with_structured_output"):
        return heuristic_select(user_text, metas)
    structured = llm.with_structured_output(SkillChoice)
    result = structured.invoke(
        [
            {
                "role": "system",
                "content": (
                    "Select exactly one skill for the user task. "
                    "Only use skill names from the catalog.\n"
                    f"{catalog}"
                ),
            },
            {"role": "user", "content": user_text or ""},
        ]
    )
    if isinstance(result, SkillChoice):
        return result
    return SkillChoice.model_validate(result)


_router: SkillRouter | None = None


def get_skill_router() -> SkillRouter:
    global _router
    if _router is None:
        _router = SkillRouter()
    return _router


def set_skill_router(router: SkillRouter | None) -> None:
    global _router
    _router = router
