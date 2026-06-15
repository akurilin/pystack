"""Create tasks table.

Revision ID: 20260615_0001
Revises:
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260615_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("backlog", "ready", "in_progress", "review", "done")


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="backlog", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="ck_tasks_position_nonnegative"),
        sa.CheckConstraint(f"status IN {STATUSES!r}", name="ck_tasks_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_status_position", "tasks", ["status", "position"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_status_position", table_name="tasks")
    op.drop_table("tasks")
