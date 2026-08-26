# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

import pytest

from src.runtime.memory.service import set_memory_service
from src.runtime.task.service import set_task_service


@pytest.fixture(autouse=True)
def _memory_runtime_stores(monkeypatch):
    """Keep unit tests off the default SQLite files so they do not share state."""
    monkeypatch.setenv("TASK_STORE_URL", "memory://")
    monkeypatch.setenv("MEMORY_STORE_URL", "memory://")
    set_task_service(None)
    set_memory_service(None)
    yield
    set_task_service(None)
    set_memory_service(None)
