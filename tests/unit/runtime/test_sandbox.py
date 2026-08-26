# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

import os

from src.runtime.sandbox import run_python
from src.tools.python_repl import python_repl_tool


def test_process_isolation_runs_in_child_and_returns_stdout():
    result = run_python("print(1 + 1)")
    assert result.ok is True
    assert result.isolated is True
    assert "2" in result.stdout


def test_process_isolation_does_not_mutate_parent_env():
    marker = "TASKPILOT_PROCESS_ISOLATION_MARKER"
    os.environ.pop(marker, None)
    result = run_python(f"import os; os.environ['{marker}'] = '1'; print('ok')")
    assert result.ok is True
    assert marker not in os.environ


def test_process_isolation_times_out():
    result = run_python("import time\ntime.sleep(5)", timeout=0.3)
    assert result.ok is False
    assert result.timed_out is True


def test_repl_disabled_does_not_execute_code():
    with _env("ENABLE_PYTHON_REPL", "false"):
        result = python_repl_tool.invoke({"code": "open('x','w').write('nope')"})
    assert "Tool disabled:" in result


def _env(key: str, value: str):
    from unittest.mock import patch

    return patch.dict(os.environ, {key: value})
