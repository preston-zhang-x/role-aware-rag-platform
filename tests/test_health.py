from fastapi.testclient import TestClient

import app.api.v1.health as health_module
from app.main import app


def test_liveness():
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_success(monkeypatch):
    monkeypatch.setattr(health_module, "check_database", lambda: None)
    monkeypatch.setattr(health_module, "check_qdrant", lambda: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
            "qdrant": "ok",
        },
    }


def test_readiness_returns_503_when_dependency_fails(monkeypatch):
    def fail_database():
        raise RuntimeError("database is down")

    monkeypatch.setattr(health_module, "check_database", fail_database)
    monkeypatch.setattr(health_module, "check_qdrant", lambda: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {
            "database": "error: RuntimeError",
            "qdrant": "ok",
        },
    }
