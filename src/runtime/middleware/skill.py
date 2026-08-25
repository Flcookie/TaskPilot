# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from typing import Any

from src.runtime.middleware.base import RuntimeContext, RuntimeMiddleware
from src.runtime.skills.loader import get_skill_loader
from src.runtime.skills.router import DEFAULT_SKILL, get_skill_router

logger = logging.getLogger(__name__)


class SkillMiddleware(RuntimeMiddleware):
    name = "skill"

    def before_planning(self, ctx: RuntimeContext, payload: dict[str, Any]) -> dict[str, Any]:
        choice = get_skill_router().select(payload.get("user_text") or "")
        skill_name = choice.name or DEFAULT_SKILL
        content = get_skill_loader().load(skill_name)
        allowed_tools = list(content.meta.allowed_tools)
        payload["selected_skills"] = [skill_name]
        payload["skill_reason"] = choice.reason
        payload["skill_context"] = content.body
        payload["allowed_tools"] = allowed_tools
        ctx.allowed_tools = allowed_tools
        ctx.extra["skill_context"] = content.body
        ctx.extra["selected_skills"] = [skill_name]
        self._persist(ctx, skill_name, choice.reason, allowed_tools)
        return payload

    def _persist(
        self,
        ctx: RuntimeContext,
        skill_name: str,
        reason: str,
        allowed_tools: list[str],
    ) -> None:
        if not ctx.task_id:
            return
        try:
            from src.runtime.task.service import get_task_service

            service = get_task_service()
            task = service.get(ctx.task_id)
            task.selected_skills = [skill_name]
            service._store.put_task(task)
            service.append_event(
                ctx.task_id,
                "skill_selected",
                {"selected_skills": [skill_name], "reason": reason},
            )
            service.append_event(
                ctx.task_id,
                "skill_loaded",
                {"selected_skills": [skill_name], "allowed_tools": allowed_tools},
            )
        except Exception:
            logger.debug("Skip skill persistence; task store unavailable", exc_info=True)
