# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from typing import Optional

from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    priority: int = 0
    path: str = ""


class SkillContent(BaseModel):
    meta: SkillMeta
    body: str


class SkillChoice(BaseModel):
    selected_skills: list[str] = Field(default_factory=list)
    reason: str = ""

    @property
    def name(self) -> Optional[str]:
        return self.selected_skills[0] if self.selected_skills else None
