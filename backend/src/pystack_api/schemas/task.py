from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from pystack_api.models.task import TaskStatus


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    status: TaskStatus
    position: int
    created_at: datetime
    updated_at: datetime
