# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.runtime.task.models import utc_now


class MemoryKind(str, Enum):
    PREFERENCE = "preference"
    BACKGROUND = "background"
    FACT = "fact"


class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    kind: MemoryKind
    content: str
    source: str = ""
    confidence: float = 0.6
    created_at: datetime = Field(default_factory=utc_now)
