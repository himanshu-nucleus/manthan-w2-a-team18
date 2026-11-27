"""Tests for the liveness and readiness probes, and for route mounting."""

from fastapi.testclient import TestClient

from app.config import Settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_configured_app_and_environment(
    client: TestClient, settings: Settings
) -> None:
    payload = client.get("/health").json()

    assert set(payload) == {"status", "app", "environment"}
    assert payload["app"] == settings.app_name
    assert payload["environment"] == settings.environment


def test_readiness_reports_database_ok(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404


def test_unknown_api_v1_route_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    # app.errors wraps every failure in one envelope, so FastAPI's default
    # {"detail": ...} is deliberately replaced.
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


def test_errors_use_the_standard_envelope(client: TestClient) -> None:
    """Every failure returns {"error": {"code", "message"}} - the frontend relies on it."""
    body = client.get("/nope").json()

    assert set(body) == {"error"}
    assert {"code", "message"} <= set(body["error"])
