from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.rerank_adapter as rerank_adapter_module
from app.rerank_adapter import app


class FakeBackend:
    device_label = "cpu"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def score(
        self,
        query: str,
        documents: list[str],
        *,
        max_tokens_per_doc: int,
    ) -> list[float]:
        self.calls.append(
            {
                "query": query,
                "documents": list(documents),
                "max_tokens_per_doc": max_tokens_per_doc,
            }
        )
        return [0.1, 0.8, 0.4]


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        rerank_model="BAAI/bge-reranker-v2-m3",
        rerank_api_key="local-rerank",
        rerank_device="cpu",
        rerank_max_length=1024,
    )


def test_health_returns_ok_when_backend_loads(monkeypatch) -> None:
    monkeypatch.setattr(
        rerank_adapter_module,
        "get_rerank_adapter_settings",
        _settings,
    )
    monkeypatch.setattr(
        rerank_adapter_module,
        "get_backend",
        lambda: FakeBackend(),
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model": "BAAI/bge-reranker-v2-m3",
        "device": "cpu",
    }


def test_health_returns_503_when_backend_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        rerank_adapter_module,
        "get_rerank_adapter_settings",
        _settings,
    )

    def fail_backend():
        raise RuntimeError("missing dependencies")

    monkeypatch.setattr(rerank_adapter_module, "get_backend", fail_backend)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["model"] == "BAAI/bge-reranker-v2-m3"
    assert "RuntimeError" in body["detail"]


def test_rerank_requires_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(
        rerank_adapter_module,
        "get_rerank_adapter_settings",
        _settings,
    )

    with TestClient(app) as client:
        response = client.post(
            "/rerank",
            json={
                "model": "BAAI/bge-reranker-v2-m3",
                "query": "test",
                "documents": ["a"],
                "top_n": 1,
                "max_tokens_per_doc": 64,
            },
        )

    assert response.status_code == 401


def test_rerank_rejects_unknown_model(monkeypatch) -> None:
    monkeypatch.setattr(
        rerank_adapter_module,
        "get_rerank_adapter_settings",
        _settings,
    )
    monkeypatch.setattr(
        rerank_adapter_module,
        "get_backend",
        lambda: FakeBackend(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/rerank",
            headers={"Authorization": "Bearer local-rerank"},
            json={
                "model": "wrong-model",
                "query": "test",
                "documents": ["a"],
                "top_n": 1,
                "max_tokens_per_doc": 64,
            },
        )

    assert response.status_code == 400
    assert "Unsupported model" in response.json()["detail"]


def test_rerank_returns_sorted_results(monkeypatch) -> None:
    backend = FakeBackend()
    monkeypatch.setattr(
        rerank_adapter_module,
        "get_rerank_adapter_settings",
        _settings,
    )
    monkeypatch.setattr(rerank_adapter_module, "get_backend", lambda: backend)

    with TestClient(app) as client:
        response = client.post(
            "/rerank",
            headers={"Authorization": "Bearer local-rerank"},
            json={
                "model": "BAAI/bge-reranker-v2-m3",
                "query": "test",
                "documents": ["first", "second", "third"],
                "top_n": 2,
                "max_tokens_per_doc": 128,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {"index": 1, "relevance_score": 0.8},
            {"index": 2, "relevance_score": 0.4},
        ]
    }
    assert backend.calls == [
        {
            "query": "test",
            "documents": ["first", "second", "third"],
            "max_tokens_per_doc": 128,
        }
    ]
