import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from pystack_api.db.base import Base


class TaskStatus(StrEnum):
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


STATUS_VALUES = tuple(status.value for status in TaskStatus)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_tasks_position_nonnegative"),
        CheckConstraint(f"status IN {STATUS_VALUES!r}", name="ck_tasks_status"),
        Index("ix_tasks_status_position", "status", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.BACKLOG.value)
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
