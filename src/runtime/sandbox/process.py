# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

"""Process-isolation demo for Python execution.

This is not a security sandbox. It only moves code out of the API process
with a timeout and a temporary working directory. A real isolation boundary
belongs in a container or micro-VM.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_WINDOWS_ENV = ("PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "windir", "PATHEXT", "COMSPEC")


@dataclass
class ProcessExecResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    timed_out: bool = False
    timeout: float = 15
    isolated: bool = True


def run_python(code: str, *, timeout: float = 15, cwd: Optional[Path] = None) -> ProcessExecResult:
    """Run Python in a child process. Isolation demo, not a security boundary."""
    workdir = Path(cwd) if cwd else None
    tmp: Optional[tempfile.TemporaryDirectory] = None
    try:
        if workdir is None:
            tmp = tempfile.TemporaryDirectory(prefix="taskpilot-exec-")
            workdir = Path(tmp.name)
        script = workdir / "_snippet.py"
        script.write_text("# -*- coding: utf-8 -*-\n" + (code or ""), encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=_child_env(),
            )
        except subprocess.TimeoutExpired:
            return ProcessExecResult(
                ok=False,
                error=f"execution exceeded {timeout}s",
                timed_out=True,
                timeout=timeout,
            )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode != 0:
            return ProcessExecResult(
                ok=False,
                stdout=stdout,
                stderr=stderr,
                error=stderr.strip() or f"exit code {completed.returncode}",
                timeout=timeout,
            )
        return ProcessExecResult(ok=True, stdout=stdout, stderr=stderr, timeout=timeout)
    finally:
        if tmp is not None:
            tmp.cleanup()


def _child_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in _WINDOWS_ENV if key in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env
