# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from src.runtime.task.models import TaskStatus
from src.runtime.task.service import TaskService, get_task_service, set_task_service
from src.runtime.task.sqlite import SqliteTaskStore, parse_sqlite_url
from src.runtime.task.store import InMemoryTaskStore, create_task_store


def test_parse_sqlite_url_relative_and_absolute():
    assert parse_sqlite_url("sqlite:///data/tasks.sqlite") == "data/tasks.sqlite"
    assert parse_sqlite_url("sqlite:////tmp/tasks.sqlite") == "/tmp/tasks.sqlite"
    assert parse_sqlite_url("data/tasks.sqlite") == "data/tasks.sqlite"


def test_sqlite_store_survives_reopen(tmp_path):
    path = tmp_path / "tasks.sqlite"
    first = SqliteTaskStore(path)
    service = TaskService(store=first)
    task = service.create(
        thread_id="thread-persist",
        input_data={"messages": [{"role": "user", "content": "hello"}]},
        selected_skills=["deep_research"],
    )
    service.start(task.id)
    service.append_event(task.id, "skill_selected", {"selected_skills": ["deep_research"]})
    service.mark_succeeded(task.id)
    first.close()

    second = SqliteTaskStore(path)
    restored = TaskService(store=second)
    loaded = restored.get(task.id)
    assert loaded.status == TaskStatus.SUCCEEDED
    assert loaded.thread_id == "thread-persist"
    assert loaded.selected_skills == ["deep_research"]
    types = [event.type for event in restored.list_events(task.id)]
    assert "task_created" in types
    assert "task_started" in types
    assert "skill_selected" in types
    after = restored.list_events(task.id, after_seq=1)
    assert all(event.seq > 1 for event in after)
    second.close()


def test_create_task_store_memory(monkeypatch):
    monkeypatch.setenv("TASK_STORE_URL", "memory://")
    store = create_task_store()
    assert isinstance(store, InMemoryTaskStore)


def test_create_task_store_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{(tmp_path / 't.sqlite').as_posix()}"
    monkeypatch.setenv("TASK_STORE_URL", url)
    store = create_task_store()
    assert isinstance(store, SqliteTaskStore)
    store.close()


def test_get_task_service_uses_factory(monkeypatch, tmp_path):
    url = f"sqlite:///{(tmp_path / 'svc.sqlite').as_posix()}"
    monkeypatch.setenv("TASK_STORE_URL", url)
    set_task_service(None)
    try:
        service = get_task_service()
        task = service.create(thread_id="t-factory")
        set_task_service(None)
        reopened = get_task_service()
        assert reopened.get(task.id).thread_id == "t-factory"
    finally:
        set_task_service(None)
