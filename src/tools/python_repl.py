# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

import logging
import os
from typing import Annotated, Optional

from langchain_core.tools import tool

from src.runtime.sandbox import run_python

from .decorators import log_io


def _is_python_repl_enabled() -> bool:
    """Check if Python execution is enabled from configuration."""
    env_enabled = os.getenv("ENABLE_PYTHON_REPL", "false").lower()
    if env_enabled in ("true", "1", "yes", "on"):
        return True
    return False


class ProcessIsolationBackend:
    """Child-process backend with the same .run() surface as PythonREPL."""

    def run(self, code: str) -> str:
        timeout = float(os.getenv("PYTHON_REPL_TIMEOUT", "15"))
        result = run_python(code, timeout=timeout)
        if result.timed_out:
            return f"TimeoutError: {result.error}"
        if not result.ok:
            return (result.stderr or result.error or "Error").strip()
        return result.stdout


repl: Optional[ProcessIsolationBackend] = (
    ProcessIsolationBackend() if _is_python_repl_enabled() else None
)
logger = logging.getLogger(__name__)


@tool
@log_io
def python_repl_tool(
    code: Annotated[
        str, "The python code to execute to do further analysis or calculation."
    ],
):
    """Use this to execute python code and do data analysis or calculation. If you want to see the output of a value,
    you should print it out with `print(...)`. This is visible to the user."""

    # Check if the tool is enabled
    if not _is_python_repl_enabled():
        error_msg = "Python REPL tool is disabled. Please enable it in environment configuration."
        logger.warning(error_msg)
        return f"Tool disabled: {error_msg}"

    if not isinstance(code, str):
        error_msg = f"Invalid input: code must be a string, got {type(code)}"
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"

    logger.info("Executing Python code")
    backend = repl or ProcessIsolationBackend()
    try:
        result = backend.run(code)
        # Check if the result is an error message by looking for typical error patterns
        if isinstance(result, str) and ("Error" in result or "Exception" in result):
            logger.error(result)
            return f"Error executing code:\n```python\n{code}\n```\nError: {result}"
        logger.info("Code execution successful")
    except BaseException as e:
        error_msg = repr(e)
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"

    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
    return result_str
