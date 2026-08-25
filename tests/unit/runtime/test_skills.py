# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from pathlib import Path

from src.graph.nodes import _filter_tools_by_skill
from src.runtime.middleware.base import RuntimeContext, build_default_stack
from src.runtime.skills.apply import apply_skill_selection
from src.runtime.skills.loader import SkillLoader
from src.runtime.skills.registry import SkillRegistry
from src.runtime.skills.router import SkillRouter, heuristic_select
from src.runtime.task.service import TaskService, set_task_service


SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"


def test_registry_loads_metadata_only():
    registry = SkillRegistry(SKILLS_DIR)
    assert set(registry.names()) == {"data_analysis", "deep_research", "report_writing"}
    research = registry.get("deep_research")
    assert research is not None
    assert "web_search" in research.allowed_tools
    assert research.path.endswith("deep_research")
    assert not hasattr(research, "body")


def test_loader_reads_skill_md_lazily():
    registry = SkillRegistry(SKILLS_DIR)
    content = SkillLoader(registry).load("deep_research")
    assert "Recommended Workflow" in content.body
    assert "Quality Rules" in content.body


def test_router_defaults_to_deep_research():
    registry = SkillRegistry(SKILLS_DIR)
    choice = heuristic_select(
        "分析英伟达过去三个季度数据中心业务变化并交叉验证信源",
        registry.all(),
    )
    assert choice.name == "deep_research"


def test_router_picks_data_analysis_for_numeric_tasks():
    registry = SkillRegistry(SKILLS_DIR)
    choice = heuristic_select("用 python 统计这份 csv 的均值", registry.all())
    assert choice.name == "data_analysis"


def test_skill_middleware_injects_one_skill_and_events():
    service = TaskService()
    set_task_service(service)
    try:
        task = service.create(input_data={"messages": [{"role": "user", "content": "调研量子计算"}]})
        payload = apply_skill_selection("调研量子计算", task_id=task.id)
        assert payload["selected_skills"] == ["deep_research"]
        assert "Deep Research Skill" in payload["skill_context"]
        assert "data_analysis" not in payload["skill_context"]
        assert "web_search" in payload["allowed_tools"]
        stored = service.get(task.id)
        assert stored.selected_skills == ["deep_research"]
        types = [event.type for event in service.list_events(task.id)]
        assert "skill_selected" in types
        assert "skill_loaded" in types
    finally:
        set_task_service(None)


def test_unknown_skill_falls_back():
    registry = SkillRegistry(SKILLS_DIR)
    router = SkillRouter(
        registry,
        selector=lambda _text, _metas: type("C", (), {"name": "missing", "reason": "x"})(),
    )
    choice = router.select("anything")
    assert choice.name == "deep_research"


def test_skill_hides_disallowed_builtin_tools():
    class _Tool:
        def __init__(self, name):
            self.name = name

    tools = [_Tool("web_search"), _Tool("python_repl_tool"), _Tool("mcp_custom")]
    visible = _filter_tools_by_skill(tools, ["python_repl"])
    assert [item.name for item in visible] == ["python_repl_tool", "mcp_custom"]


def test_default_stack_includes_skill_hook():
    assert "skill" in build_default_stack().names
    payload = build_default_stack().invoke(
        "before_planning",
        RuntimeContext(),
        {"user_text": "写一篇已有材料的润色报告"},
    )
    assert payload["selected_skills"] == ["report_writing"]
