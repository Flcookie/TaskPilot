# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from src.runtime.skills.models import SkillContent, SkillMeta
from src.runtime.skills.registry import SkillRegistry, get_skill_registry


class SkillLoader:
    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self._registry = registry

    @property
    def registry(self) -> SkillRegistry:
        return self._registry or get_skill_registry()

    def load(self, name: str) -> SkillContent:
        meta = self.registry.get(name)
        if meta is None:
            raise KeyError(f"Skill '{name}' is not registered")
        body_path = Path(meta.path) / "SKILL.md"
        body = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
        return SkillContent(meta=meta, body=body)

    def load_many(self, names: list[str]) -> list[SkillContent]:
        return [self.load(name) for name in names]


_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader


def set_skill_loader(loader: SkillLoader | None) -> None:
    global _loader
    _loader = loader
