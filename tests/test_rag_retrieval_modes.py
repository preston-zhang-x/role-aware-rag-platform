from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import app.services.rag_service as rag_service_module
from app.services.bm25_service import BM25Hit
from app.services.rag_service import RagService
from app.services.reranker_service import (
    RerankResult,
    RerankerConfigurationError,
    RerankerTransientError,
)


@dataclass
class FakePoint:
    payload: dict[str, Any]
    score: float


@dataclass
class FakeQueryResult:
    points: list[FakePoint]


class FakeBM25Service:
    def __init__(self, hits: list[BM25Hit]) -> None:
        self.hits = hits
        self.search_calls: list[tuple[str, int | None]] = []

    def search(self, query: str, top_k: int | None = None) -> list[BM25Hit]:
        self.search_calls.append((query, top_k))
        if top_k is None:
            return list(self.hits)
        return list(self.hits[:top_k])


class FakeRerankerClient:
    def __init__(
        self,
        results: list[RerankResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = list(results or [])
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def rerank(
        self,
        query: str,
        chunks: list[Any],
        top_n: int,
    ) -> list[RerankResult]:
        self.calls.append(
            {
                "query": query,
                "chunks": list(chunks),
                "top_n": top_n,
            }
        )
        if self.error is not None:
            raise self.error
        return list(self.results)


@pytest.fixture
def mock_openai_client():
    fake_embedding = [0.1] * 8

    with patch("app.services.rag_service.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        embedding_response = MagicMock()
        embedding_response.data = [MagicMock(embedding=fake_embedding)]
        mock_client.embeddings.create.return_value = embedding_response

        yield mock_client


def _vector_points() -> list[FakePoint]:
    return [
        FakePoint(
            payload={
                "text": "alpha body",
                "source_file": "alpha.md",
                "chunk_index": 0,
                "allowed_roles": ["staff"],
                "formula_description": "alpha formula",
            },
            score=0.91,
        ),
        FakePoint(
            payload={
                "text": "beta body",
                "source_file": "beta.md",
                "chunk_index": 1,
                "allowed_roles": ["staff"],
            },
            score=0.82,
        ),
    ]


def _bm25_hits() -> list[BM25Hit]:
    return [
        BM25Hit(
            text="beta body",
            source_file="beta.md",
            score=8.5,
            chunk_index=1,
            payload={"source_file": "beta.md", "chunk_index": 1},
        ),
        BM25Hit(
            text="gamma body",
            source_file="gamma.md",
            score=6.0,
            chunk_index=2,
            payload={"source_file": "gamma.md", "chunk_index": 2},
        ),
    ]


def _build_service(
    *,
    retrieval_mode: str,
    mock_openai_client: MagicMock,
    vector_points: list[FakePoint] | None = None,
    bm25_hits: list[BM25Hit] | None = None,
    reranker_client: FakeRerankerClient | None = None,
    top_k: int = 5,
) -> tuple[RagService, MagicMock, FakeBM25Service]:
    wrapper = MagicMock()
    wrapper.client.query_points.return_value = FakeQueryResult(points=vector_points or [])
    fake_bm25 = FakeBM25Service(bm25_hits or [])
    provider_calls: list[dict[str, Any]] = []

    def bm25_provider(**kwargs: Any) -> FakeBM25Service:
        provider_calls.append(dict(kwargs))
        return fake_bm25

    service = RagService(
        qdrant_wrapper=wrapper,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        bm25_provider=bm25_provider,
        reranker_client=reranker_client,
    )
    service.openai_client = mock_openai_client
    service._generate = MagicMock(return_value="ok")
    wrapper.provider_calls = provider_calls
    return service, wrapper, fake_bm25


def test_vector_mode_only_uses_qdrant(mock_openai_client: MagicMock) -> None:
    service, wrapper, fake_bm25 = _build_service(
        retrieval_mode="vector",
        mock_openai_client=mock_openai_client,
        vector_points=_vector_points(),
        bm25_hits=_bm25_hits(),
        top_k=3,
    )

    result = service.ask("alpha", user_roles=["staff"])

    assert len(result.sources) == 2
    assert result.sources[0].source_file == "alpha.md"
    assert wrapper.client.query_points.call_args.kwargs["limit"] == 3
    assert fake_bm25.search_calls == []
    assert mock_openai_client.embeddings.create.called


def test_bm25_mode_only_uses_sparse_search(mock_openai_client: MagicMock) -> None:
    service, wrapper, fake_bm25 = _build_service(
        retrieval_mode="bm25",
        mock_openai_client=mock_openai_client,
        vector_points=_vector_points(),
        bm25_hits=_bm25_hits(),
        top_k=2,
    )

    result = service.ask("beta", user_roles=["staff"])

    assert [source.source_file for source in result.sources] == ["beta.md", "gamma.md"]
    assert wrapper.client.query_points.call_count == 0
    assert fake_bm25.search_calls == [("beta", 2)]
    assert mock_openai_client.embeddings.create.call_count == 0


def test_hybrid_mode_uses_candidate_top_k_without_reranker(
    mock_openai_client: MagicMock,
) -> None:
    service, wrapper, fake_bm25 = _build_service(
        retrieval_mode="hybrid",
        mock_openai_client=mock_openai_client,
        vector_points=_vector_points(),
        bm25_hits=_bm25_hits(),
        top_k=3,
    )

    result = service.ask("beta", user_roles=["staff"])

    assert service.candidate_top_k == 20
    assert len(result.sources) == 3
    assert wrapper.client.query_points.call_args.kwargs["limit"] == 20
    assert fake_bm25.search_calls == [("beta", 20)]


def test_hybrid_rerank_reorders_hybrid_results(mock_openai_client: MagicMock) -> None:
    reranker_client = FakeRerankerClient(
        results=[RerankResult(index=1), RerankResult(index=0)]
    )
    service, _, _ = _build_service(
        retrieval_mode="hybrid_rerank",
        mock_openai_client=mock_openai_client,
        vector_points=_vector_points(),
        bm25_hits=_bm25_hits(),
        reranker_client=reranker_client,
        top_k=2,
    )

    sources = service._retrieve_sources("beta", user_roles=["staff"])

    assert [source.source_file for source in sources] == ["alpha.md", "beta.md"]
    assert reranker_client.calls[0]["top_n"] == 2
    assert len(reranker_client.calls[0]["chunks"]) == 3


def test_hybrid_rerank_falls_back_to_hybrid_on_transient_error(
    mock_openai_client: MagicMock,
) -> None:
    reranker_client = FakeRerankerClient(
        error=RerankerTransientError("temporary failure")
    )
    service, _, _ = _build_service(
        retrieval_mode="hybrid_rerank",
        mock_openai_client=mock_openai_client,
        vector_points=_vector_points(),
        bm25_hits=_bm25_hits(),
        reranker_client=reranker_client,
        top_k=2,
    )

    sources = service._retrieve_sources("beta", user_roles=["staff"])

    assert [source.source_file for source in sources] == ["beta.md", "alpha.md"]


def test_hybrid_rerank_requires_reranker_configuration(
    mock_openai_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rag_service_module,
        "get_retrieval_settings",
        lambda: SimpleNamespace(
            top_k=5,
            retrieval_mode="hybrid",
            rerank_base_url=None,
            rerank_api_key=None,
            rerank_model=None,
            rerank_timeout_seconds=8.0,
        ),
    )

    with pytest.raises(RerankerConfigurationError):
        RagService(
            qdrant_wrapper=MagicMock(),
            retrieval_mode="hybrid_rerank",
        )
