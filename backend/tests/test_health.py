"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import DatabaseRouter, get_router
from app.main import app


def test_health_reports_database_and_ai(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["integrations"] == {"database_reachable": True, "ai_configured": False}


def test_health_when_database_is_down() -> None:
    # Nothing listens on port 1: the database is unreachable, health still answers.
    down = DatabaseRouter(admin_url="postgresql://x:x@127.0.0.1:1/postgres")
    app.dependency_overrides[get_router] = lambda: down
    try:
        with TestClient(app) as client:
            response = client.get("/api/health")
            dashboard = client.get("/api/dashboard")
    finally:
        app.dependency_overrides.clear()
        down.dispose()

    assert response.json()["integrations"]["database_reachable"] is False
    assert dashboard.status_code == 401


def test_openapi_document_is_exposed(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    for path in (
        "/api/health",
        "/api/auth/login",
        "/api/auth/me",
        "/api/auth/demo-users",
        "/api/dashboard",
        "/api/agent/analyze",
        "/api/agent/execute/initiate",
        "/api/agent/execute",
        "/api/agent/reset",
    ):
        assert path in paths
    assert not any(p.startswith("/api/scenarios") for p in paths)
