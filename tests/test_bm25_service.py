from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.bm25_service import BM25Service, tokenize


@dataclass
class FakeRecord:
    payload: dict[str, Any]


class FakeQdrantClient:
    def __init__(self, responses: list[tuple[list[FakeRecord], object | None]]) -> None:
        self._responses = list(responses)
        self.scroll_calls: list[dict[str, Any]] = []

    def scroll(self, **kwargs: Any) -> tuple[list[FakeRecord], object | None]:
        self.scroll_calls.append(dict(kwargs))
        return self._responses.pop(0)


class FakeQdrantWrapper:
    def __init__(
        self,
        responses: list[tuple[list[FakeRecord], object | None]],
        *,
        exists: bool = True,
    ) -> None:
        self.client = FakeQdrantClient(responses)
        self.exists = exists

    def collection_exists(self, collection_name: str) -> bool:
        return self.exists


def test_tokenize_uses_sudachi_normalization() -> None:
    tokens = tokenize("パンを食べました。Python、PYTHON!")

    assert "パン" in tokens
    assert "食べる" in tokens
    assert tokens.count("python") == 2
    assert "。" not in tokens


def test_build_index_filters_empty_documents_and_keeps_searchable_payloads() -> None:
    wrapper = FakeQdrantWrapper(
        responses=[
            (
                [
                    FakeRecord(
                        payload={
                            "_node_content": '{"text": "OpenAI search platform"}',
                            "source_file": "guide.md",
                            "chunk_index": 1,
                        }
                    ),
                    FakeRecord(
                        payload={
                            "text": "   ",
                            "source_file": "blank.md",
                        }
                    ),
                    FakeRecord(
                        payload={
                            "text": "Budget report for finance team",
                            "source_file": "finance.md",
                            "chunk_index": 3,
                        }
                    ),
                ],
                None,
            )
        ]
    )
    service = BM25Service(qdrant_wrapper=wrapper)

    indexed_count = service.build_index(user_roles=["staff"])

    assert indexed_count == 2
    assert service.is_indexed is True
    assert service.corpus_size == 2
    assert wrapper.client.scroll_calls[0]["scroll_filter"] is not None


def test_search_returns_ranked_hits() -> None:
    wrapper = FakeQdrantWrapper(
        responses=[
            (
                [
                    FakeRecord(
                        payload={
                            "text": "OpenAI search platform for internal docs",
                            "source_file": "guide.md",
                            "chunk_index": 1,
                        }
                    ),
                    FakeRecord(
                        payload={
                            "text": "Budget report for finance team",
                            "source_file": "finance.md",
                            "chunk_index": 3,
                        }
                    ),
                    FakeRecord(
                        payload={
                            "text": "Weekly cafeteria menu for all staff",
                            "source_file": "lunch.md",
                            "chunk_index": 4,
                        }
                    ),
                ],
                None,
            )
        ]
    )
    service = BM25Service(qdrant_wrapper=wrapper)
    service.build_index()

    hits = service.search("OpenAI platform", top_k=2)

    assert len(hits) == 1
    assert hits[0].source_file == "guide.md"
    assert hits[0].chunk_index == 1
    assert hits[0].score > 0


def test_build_index_clears_state_when_collection_is_missing() -> None:
    service = BM25Service(
        qdrant_wrapper=FakeQdrantWrapper(responses=[], exists=False),
    )

    indexed_count = service.build_index()

    assert indexed_count == 0
    assert service.is_indexed is False
    assert service.corpus_size == 0
