from uuid import UUID

from fastapi.testclient import TestClient


def test_health_reports_database_up(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}
    UUID(response.headers["x-request-id"])
