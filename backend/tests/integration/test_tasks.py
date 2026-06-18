from collections.abc import Callable
from typing import cast
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

from pystack_api.core.config import get_settings
from pystack_api.queries import tasks as task_queries

settings = get_settings()


def create_task(client: TestClient, title: str) -> dict[str, object]:
    response = client.post("/api/v1/tasks", json={"title": title, "description": ""})
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_task_lifecycle(client: TestClient) -> None:
    task = create_task(client, "First task")
    task_id = task["id"]

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Updated task", "description": "More detail"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated task"

    response = client.post(
        f"/api/v1/tasks/{task_id}/move",
        json={"status": "in_progress", "position": 0},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

    response = client.delete(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 204
    assert client.get("/api/v1/tasks").json() == []


def test_reorders_tasks_and_normalizes_positions(client: TestClient) -> None:
    first = create_task(client, "First")
    create_task(client, "Second")
    third = create_task(client, "Third")

    response = client.post(
        f"/api/v1/tasks/{third['id']}/move",
        json={"status": "backlog", "position": 0},
    )
    assert response.status_code == 200

    tasks = client.get("/api/v1/tasks").json()
    assert [(task["title"], task["position"]) for task in tasks] == [
        ("Third", 0),
        ("First", 1),
        ("Second", 2),
    ]

    response = client.post(
        f"/api/v1/tasks/{first['id']}/move",
        json={"status": "done", "position": 99},
    )
    assert response.status_code == 200
    assert response.json()["position"] == 0


def test_validates_input_and_returns_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/tasks", json={"title": ""})
    assert response.status_code == 422

    missing_id = "00000000-0000-0000-0000-000000000000"
    response = client.patch(f"/api/v1/tasks/{missing_id}", json={"title": "Missing"})
    assert response.status_code == 404


def test_tasks_are_isolated_per_user(client_as: Callable[[str], TestClient]) -> None:
    alice = client_as("user_alice")
    bob = client_as("user_bob")

    task = create_task(alice, "Alice's task")
    task_id = task["id"]

    # Bob has his own empty board and cannot see or touch Alice's task.
    assert bob.get("/api/v1/tasks").json() == []
    assert bob.patch(f"/api/v1/tasks/{task_id}", json={"title": "hijack"}).status_code == 404
    assert (
        bob.post(
            f"/api/v1/tasks/{task_id}/move", json={"status": "done", "position": 0}
        ).status_code
        == 404
    )
    assert bob.delete(f"/api/v1/tasks/{task_id}").status_code == 404

    # Alice's task is untouched.
    assert [t["title"] for t in alice.get("/api/v1/tasks").json()] == ["Alice's task"]


def test_database_rejects_duplicate_positions_for_same_user_and_column() -> None:
    # The task ordering constraint is deferrable, so PostgreSQL raises when
    # the transaction commits, not necessarily on the second INSERT.
    user_id = "user_invariant"
    with (
        pytest.raises(psycopg.errors.UniqueViolation),
        psycopg.connect(settings.test_database_url) as connection,
    ):
        connection.execute(
            task_queries.insert_task_query(
                task_id=UUID("00000000-0000-0000-0000-000000000001"),
                user_id=user_id,
                title="One",
                description="",
                status="backlog",
                position=0,
            )
        )
        connection.execute(
            task_queries.insert_task_query(
                task_id=UUID("00000000-0000-0000-0000-000000000002"),
                user_id=user_id,
                title="Two",
                description="",
                status="backlog",
                position=0,
            )
        )


def test_positions_are_independent_per_user_and_column() -> None:
    with psycopg.connect(settings.test_database_url) as connection:
        connection.execute(
            task_queries.insert_task_query(
                task_id=UUID("00000000-0000-0000-0000-000000000003"),
                user_id="user_a",
                title="A backlog",
                description="",
                status="backlog",
                position=0,
            )
        )
        connection.execute(
            task_queries.insert_task_query(
                task_id=UUID("00000000-0000-0000-0000-000000000004"),
                user_id="user_a",
                title="A ready",
                description="",
                status="ready",
                position=0,
            )
        )
        connection.execute(
            task_queries.insert_task_query(
                task_id=UUID("00000000-0000-0000-0000-000000000005"),
                user_id="user_b",
                title="B backlog",
                description="",
                status="backlog",
                position=0,
            )
        )
