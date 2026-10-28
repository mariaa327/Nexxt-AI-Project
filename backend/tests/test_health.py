"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_without_credentials() -> None:
    # A plain client (no dependency overrides) proves the endpoint works with
    # no database, Supabase or AI configuration.
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["integrations"] == {
        "database_configured": False,
        "supabase_auth_configured": False,
        "ai_configured": False,
    }


def test_openapi_document_is_exposed() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/health" in paths
    assert "/api/agent/run" in paths
