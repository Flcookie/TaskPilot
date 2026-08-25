# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolErrorKind(str, Enum):
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    UPSTREAM = "upstream"
    UNKNOWN = "unknown"


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: Optional[str] = None
    error_kind: Optional[ToolErrorKind] = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def success(cls, data: Any, **meta: Any) -> "ToolResult":
        return cls(ok=True, data=data, meta=meta)

    @classmethod
    def fail(
        cls,
        error: str,
        error_kind: ToolErrorKind = ToolErrorKind.UNKNOWN,
        **meta: Any,
    ) -> "ToolResult":
        return cls(ok=False, error=error, error_kind=error_kind, meta=meta)

    def to_agent_content(self) -> Any:
        """Successful calls keep the original payload; failures use a stable error contract."""
        if self.ok:
            return self.data
        return {
            "ok": False,
            "error": self.error,
            "error_kind": self.error_kind.value if self.error_kind else ToolErrorKind.UNKNOWN.value,
            "meta": self.meta,
        }

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False)
