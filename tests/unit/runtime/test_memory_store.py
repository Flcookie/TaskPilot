# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from src.runtime.memory.models import MemoryKind
from src.runtime.memory.service import (
    MemoryService,
    get_memory_service,
    set_memory_service,
)
from src.runtime.memory.sqlite import SqliteMemoryStore
from src.runtime.memory.store import InMemoryMemoryStore, create_memory_store
from src.runtime.skills.apply import apply_skill_selection


def test_sqlite_memory_survives_reopen(tmp_path):
    path = tmp_path / "memory.sqlite"
    first = SqliteMemoryStore(path)
    service = MemoryService(store=first)
    service.write(
        user_id="alice",
        kind=MemoryKind.BACKGROUND,
        content="User previously researched NVIDIA",
    )
    service.write(
        user_id="alice",
        kind=MemoryKind.PREFERENCE,
        content="Preferred locale is zh-CN",
    )
    first.close()

    second = SqliteMemoryStore(path)
    restored = MemoryService(store=second)
    items = restored.retrieve("alice", "NVIDIA")
    joined = " ".join(item.content for item in items)
    assert "NVIDIA" in joined
    assert "zh-CN" in joined
    kinds = {item.kind for item in items}
    assert MemoryKind.BACKGROUND in kinds
    assert MemoryKind.PREFERENCE in kinds
    second.close()


def test_sqlite_memory_upserts_same_kind_and_content(tmp_path):
    store = SqliteMemoryStore(tmp_path / "memory.sqlite")
    service = MemoryService(store=store)
    first = service.write(user_id="bob", kind=MemoryKind.FACT, content="same fact")
    second = service.write(user_id="bob", kind=MemoryKind.FACT, content="same fact")
    assert first is not None and second is not None
    items = store.list_for_user("bob", MemoryKind.FACT)
    assert len(items) == 1
    assert items[0].id == second.id
    store.close()


def test_create_memory_store_memory(monkeypatch):
    monkeypatch.setenv("MEMORY_STORE_URL", "memory://")
    store = create_memory_store()
    assert isinstance(store, InMemoryMemoryStore)


def test_create_memory_store_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.sqlite').as_posix()}"
    monkeypatch.setenv("MEMORY_STORE_URL", url)
    store = create_memory_store()
    assert isinstance(store, SqliteMemoryStore)
    store.close()


def test_second_task_after_restart_sees_memory(monkeypatch, tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.sqlite').as_posix()}"
    monkeypatch.setenv("MEMORY_STORE_URL", url)
    set_memory_service(None)
    try:
        memory = get_memory_service()
        memory.write(
            user_id="alice",
            kind=MemoryKind.BACKGROUND,
            content="User previously researched NVIDIA datacenter",
        )
        memory.write(
            user_id="alice",
            kind=MemoryKind.PREFERENCE,
            content="Preferred locale is zh-CN",
        )
        set_memory_service(None)
        payload = apply_skill_selection("继续分析英伟达数据中心", user_id="alice")
        assert "NVIDIA" in payload["memory_context"]
        assert "zh-CN" in payload["memory_context"]
    finally:
        set_memory_service(None)
