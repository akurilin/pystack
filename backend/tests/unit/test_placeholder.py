"""Pure unit tests: no database, no fixtures, no network.

Tests in this package must stay free of I/O so they run instantly and in
isolation. Anything that needs the database belongs under ``tests/integration``
instead, where the DB fixtures live. Run just this fast lane with
``uv run pytest tests/unit``.

The test below is a placeholder seed — replace or extend it as genuinely
DB-independent logic appears. It exercises a pure Pydantic validator to show the
intended Arrange-Act-Assert shape.
"""

import pytest
from pydantic import ValidationError

from pystack_api.schemas import TaskCreate


def test_task_create_defaults_description_to_empty_string() -> None:
    task = TaskCreate(title="Write release notes")

    assert task.description == ""


def test_task_create_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="")
