from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

import app.services.reranker_service as reranker_service_module
from app.services.reranker_service import (
    CohereCompatibleRerankerClient,
    RerankerConfigurationError,
    RerankerTransientError,
)


@dataclass
class DummyChunk:
    text: str
    source_file: str
    chunk_index: int
    payload: dict[str, Any] = field(default_factory=dict)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any,
        *,
        json_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self) -> Any:
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://example.com/rerank")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "rerank request failed",
                request=request,
                response=response,
            )


def test_reranker_requires_complete_configuration() -> None:
    with pytest.raises(RerankerConfigurationError):
        CohereCompatibleRerankerClient(
            base_url="",
            api_key="token",
            model="rerank-v3.5",
        )


def test_reranker_formats_documents_and_parses_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(
            200,
            {
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.75},
                ]
            },
        )

    monkeypatch.setattr(reranker_service_module.httpx, "post", fake_post)
    client = CohereCompatibleRerankerClient(
        base_url="https://gateway.example/v2",
        api_key="secret",
        model="rerank-v3.5",
        timeout_seconds=4.0,
    )
    chunks = [
        DummyChunk(
            text="plain body",
            source_file="guide.md",
            chunk_index=0,
        ),
        DummyChunk(
            text="SUM(A1:A10)",
            source_file="sheet.xlsx",
            chunk_index=2,
            payload={"formula_description": "Excel formula summary"},
        ),
    ]

    results = client.rerank("how to use", chunks, top_n=2)

    assert [result.index for result in results] == [1, 0]
    assert captured["url"] == "https://gateway.example/v2/rerank"
    documents = captured["kwargs"]["json"]["documents"]
    assert "source_file: guide.md" in documents[0]
    assert "formula_description: Excel formula summary" in documents[1]
    assert "text: |" in documents[1]
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer secret"
    assert captured["kwargs"]["timeout"] == 4.0


def test_reranker_raises_transient_error_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(reranker_service_module.httpx, "post", fake_post)
    client = CohereCompatibleRerankerClient(
        base_url="https://gateway.example/v2",
        api_key="secret",
        model="rerank-v3.5",
    )

    with pytest.raises(RerankerTransientError):
        client.rerank(
            "how to use",
            [DummyChunk(text="body", source_file="guide.md", chunk_index=0)],
            top_n=1,
        )


def test_reranker_raises_transient_error_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, None, json_error=ValueError("not json"))

    monkeypatch.setattr(reranker_service_module.httpx, "post", fake_post)
    client = CohereCompatibleRerankerClient(
        base_url="https://gateway.example/v2",
        api_key="secret",
        model="rerank-v3.5",
    )

    with pytest.raises(RerankerTransientError):
        client.rerank(
            "how to use",
            [DummyChunk(text="body", source_file="guide.md", chunk_index=0)],
            top_n=1,
        )


def test_reranker_raises_transient_error_on_missing_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, {"id": "abc"})

    monkeypatch.setattr(reranker_service_module.httpx, "post", fake_post)
    client = CohereCompatibleRerankerClient(
        base_url="https://gateway.example/v2",
        api_key="secret",
        model="rerank-v3.5",
    )

    with pytest.raises(RerankerTransientError):
        client.rerank(
            "how to use",
            [DummyChunk(text="body", source_file="guide.md", chunk_index=0)],
            top_n=1,
        )
