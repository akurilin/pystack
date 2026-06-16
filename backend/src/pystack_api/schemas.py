from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class TaskMove(BaseModel):
    status: TaskStatus
    position: int = Field(ge=0)


class TaskRead(BaseModel):
    id: UUID
    title: str
    description: str
    status: TaskStatus
    position: int
    created_at: datetime
    updated_at: datetime


class AssistantChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class AssistantChatRequest(BaseModel):
    messages: list[AssistantChatMessage] = Field(default_factory=list, max_length=50)
