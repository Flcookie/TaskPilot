# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from src.runtime.memory.models import MemoryKind
from src.runtime.memory.service import MemoryService, set_memory_service
from src.runtime.middleware.base import RuntimeContext, build_default_stack
from src.runtime.skills.apply import apply_skill_selection
from src.runtime.task.service import TaskService, set_task_service
from src.runtime.tools.result import ToolResult


def test_retrieve_respects_top_k_and_token_budget():
    service = MemoryService()
    service.write(user_id="u1", kind=MemoryKind.FACT, content="NVIDIA datacenter revenue grew")
    service.write(user_id="u1", kind=MemoryKind.BACKGROUND, content="User previously researched NVIDIA")
    service.write(user_id="u1", kind=MemoryKind.PREFERENCE, content="Preferred locale is zh-CN")
    service.write(
        user_id="u1",
        kind=MemoryKind.FACT,
        content="x" * 2000,
    )
    items = service.retrieve("u1", "NVIDIA datacenter", top_k=2, token_budget=80)
    assert 1 <= len(items) <= 2
    joined = " ".join(item.content for item in items)
    assert "NVIDIA" in joined
    assert len(service.format_context(items)) <= 80 * 4 + 80


def test_second_task_sees_previous_background_and_preference():
    memory = MemoryService()
    set_memory_service(memory)
    tasks = TaskService()
    set_task_service(tasks)
    try:
        first = tasks.create(
            user_id="alice",
            thread_id="t-a",
            input_data={"messages": [{"role": "user", "content": "调研英伟达数据中心"}]},
        )
        stack = build_default_stack()
        ctx = RuntimeContext(task_id=first.id, extra={"user_id": "alice"})
        stack.invoke(
            "after_task",
            ctx,
            {
                "status": "succeeded",
                "user_id": "alice",
                "user_text": "调研英伟达数据中心",
                "locale": "zh-CN",
            },
        )
        second = apply_skill_selection("继续分析英伟达数据中心", user_id="alice")
        assert "英伟达" in second["memory_context"]
        assert "zh-CN" in second["memory_context"]
        assert "[background]" in second["memory_context"]
        assert "[preference]" in second["memory_context"]
    finally:
        set_memory_service(None)
        set_task_service(None)


def test_memory_write_skips_failed_tool_results():
    memory = MemoryService()
    set_memory_service(memory)
    try:
        stack = build_default_stack()
        stack.invoke(
            "after_tool",
            RuntimeContext(),
            {
                "user_id": "bob",
                "name": "web_search",
                "result": ToolResult.fail("timeout exploded"),
            },
        )
        assert memory.retrieve("bob", "timeout") == []
    finally:
        set_memory_service(None)


def test_context_inject_is_the_only_prompt_writer():
    memory = MemoryService()
    set_memory_service(memory)
    try:
        memory.write(
            user_id="carol",
            kind=MemoryKind.FACT,
            content="Quantum computing needs error correction",
        )
        payload = build_default_stack().invoke(
            "before_planning",
            RuntimeContext(extra={"user_id": "carol"}),
            {"user_text": "quantum computing", "user_id": "carol"},
        )
        assert "Quantum computing" in payload["memory_context"]
        assert payload["selected_skills"]
    finally:
        set_memory_service(None)
