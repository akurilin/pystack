import psycopg
import pytest
from fastapi.testclient import TestClient

from pystack_api.core.config import get_settings
from pystack_api.main import create_app
from pystack_api.services.assistant import execute_task_tool

settings = get_settings()


def test_assistant_task_tools_mutate_board() -> None:
    with psycopg.connect(settings.test_database_url) as connection:
        created = execute_task_tool(
            connection,
            "create_task",
            {"title": "Draft release notes", "description": "Summarize changes"},
        )
        task_id = created.content["task"]["id"]

        moved = execute_task_tool(
            connection,
            "move_task",
            {"task_id": task_id, "status": "ready", "position": 0},
        )
        listed = execute_task_tool(connection, "list_tasks", {})

    assert created.mutated
    assert created.content["task"]["status"] == "backlog"
    assert moved.mutated
    assert moved.content["task"]["status"] == "ready"
    assert listed.content["total"] == 1
    assert listed.content["counts"]["ready"] == 1


def test_app_startup_requires_openrouter_key() -> None:
    test_settings = settings.model_copy(
        update={
            "database_url": settings.test_database_url,
            "openrouter_api_key": None,
        }
    )

    with (
        pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"),
        TestClient(create_app(test_settings)),
    ):
        pass
