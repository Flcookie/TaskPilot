# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from src.runtime.skills.models import SkillMeta

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"


class SkillRegistry:
    """Startup discovery: read skill.yaml only, never SKILL.md."""

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self._metas: dict[str, SkillMeta] = {}
        self.reload()

    def reload(self) -> None:
        self._metas.clear()
        if not self.skills_dir.exists():
            logger.warning("Skill directory does not exist: %s", self.skills_dir)
            return
        for skill_yaml in sorted(self.skills_dir.glob("*/skill.yaml")):
            with skill_yaml.open("r", encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}
            meta = SkillMeta.model_validate({**raw, "path": str(skill_yaml.parent)})
            self._metas[meta.name] = meta
            logger.info("Skill metadata loaded: %s", meta.name)

    def get(self, name: str) -> Optional[SkillMeta]:
        return self._metas.get(name)

    def all(self) -> list[SkillMeta]:
        return sorted(self._metas.values(), key=lambda item: (-item.priority, item.name))

    def names(self) -> list[str]:
        return [meta.name for meta in self.all()]


_registry: Optional[SkillRegistry] = None


def get_skill_registry(skills_dir: Optional[Path] = None) -> SkillRegistry:
    global _registry
    if _registry is None or skills_dir is not None:
        _registry = SkillRegistry(skills_dir)
    return _registry


def set_skill_registry(registry: Optional[SkillRegistry]) -> None:
    global _registry
    _registry = registry
