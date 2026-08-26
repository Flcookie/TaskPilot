# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

import pytest

from src.runtime.task.service import set_task_service


@pytest.fixture(autouse=True)
def _memory_task_store(monkeypatch):
    """Keep unit tests off the default SQLite file so they do not share events."""
    monkeypatch.setenv("TASK_STORE_URL", "memory://")
    set_task_service(None)
    yield
    set_task_service(None)
