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
    monkeypatch.setattr(health_module, "check_model_provider", lambda: None)
    monkeypatch.setattr(health_module, "check_reranker_service", lambda: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
            "qdrant": "ok",
            "models": "ok",
            "reranker": "ok",
        },
    }


def test_readiness_returns_503_when_dependency_fails(monkeypatch):
    def fail_database():
        raise RuntimeError("database is down")

    monkeypatch.setattr(health_module, "check_database", fail_database)
    monkeypatch.setattr(health_module, "check_qdrant", lambda: None)
    monkeypatch.setattr(health_module, "check_model_provider", lambda: None)
    monkeypatch.setattr(health_module, "check_reranker_service", lambda: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {
            "database": "error: RuntimeError",
            "qdrant": "ok",
            "models": "ok",
            "reranker": "ok",
        },
    }


def test_readiness_returns_503_when_model_provider_fails(monkeypatch):
    monkeypatch.setattr(health_module, "check_database", lambda: None)
    monkeypatch.setattr(health_module, "check_qdrant", lambda: None)
    monkeypatch.setattr(
        health_module,
        "check_model_provider",
        lambda: (_ for _ in ()).throw(ValueError("missing models")),
    )
    monkeypatch.setattr(health_module, "check_reranker_service", lambda: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {
            "database": "ok",
            "qdrant": "ok",
            "models": "error: ValueError",
            "reranker": "ok",
        },
    }


def test_check_model_provider_accepts_latest_alias(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "data": [
                    {"id": "qwen3.5:4b"},
                    {"id": "bge-m3:latest"},
                ]
            }

    class FakeSettings:
        openai_base_url = "http://localhost:11434/v1"
        openai_api_key = "ollama"
        chat_model = "qwen3.5:4b"
        embedding_model = "bge-m3"

    monkeypatch.setattr(health_module, "get_openai_settings", lambda: FakeSettings())
    monkeypatch.setattr(health_module.httpx, "get", lambda *args, **kwargs: FakeResponse())

    health_module.check_model_provider()
