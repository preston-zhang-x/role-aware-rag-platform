"""tests/test_rag_service_branches.py

rag_service.py の未カバーブランチを 100% にするための追加テスト。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.bm25_service import BM25Hit
from app.services.rag_service import (
    DEFAULT_CANDIDATE_TOP_K,
    FALLBACK_ANSWER,
    RagResult,
    RagService,
    SourceChunk,
)
from app.services.reranker_service import RerankResult


# ── 共通ヘルパー ─────────────────────────────────────────────


@dataclass
class FakePoint:
    payload: dict[str, Any]
    score: float


@dataclass
class FakeQueryResult:
    points: list[FakePoint]


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


def _build_service(
    mock_openai_client: MagicMock,
    retrieval_mode: str = "vector",
    top_k: int = 5,
) -> tuple[RagService, MagicMock]:
    wrapper = MagicMock()
    wrapper.client.query_points.return_value = FakeQueryResult(points=[])
    service = RagService(
        qdrant_wrapper=wrapper,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
    )
    service.openai_client = mock_openai_client
    return service, wrapper


# ── _extract_text ブランチカバレッジ ─────────────────────────


class TestExtractTextBranches:
    """_extract_text の全分岐をテストする。"""

    def test_node_content_is_none_uses_text_field(
        self, mock_openai_client: MagicMock
    ) -> None:
        """_node_content が None → payload["text"] を使う。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text({"text": "fallback text"})
        assert text == "fallback text"

    def test_node_content_is_none_and_no_text_field(
        self, mock_openai_client: MagicMock
    ) -> None:
        """_node_content も text もない → 空文字。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text({})
        assert text == ""

    def test_node_content_is_dict(self, mock_openai_client: MagicMock) -> None:
        """_node_content が dict → dict["text"] を使う。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text({"_node_content": {"text": "from dict"}})
        assert text == "from dict"

    def test_node_content_is_dict_without_text(
        self, mock_openai_client: MagicMock
    ) -> None:
        """_node_content が dict だが text キーなし → 空文字。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text({"_node_content": {"other": "data"}})
        assert text == ""

    def test_node_content_is_json_string_parsed_to_dict(
        self, mock_openai_client: MagicMock
    ) -> None:
        """_node_content が JSON 文字列で dict にパースされる。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text(
            {"_node_content": '{"text": "parsed from json"}'}
        )
        assert text == "parsed from json"

    def test_node_content_is_json_string_parsed_to_non_dict(
        self, mock_openai_client: MagicMock
    ) -> None:
        """_node_content が JSON 文字列だが dict ではない（list）→ str(parsed)。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text({"_node_content": '["a", "b"]'})
        assert text == "['a', 'b']"

    def test_node_content_is_invalid_json_string(
        self, mock_openai_client: MagicMock
    ) -> None:
        """_node_content が無効な JSON → そのまま文字列を返す。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text({"_node_content": "{not json}"})
        assert text == "{not json}"

    def test_node_content_is_arbitrary_type(
        self, mock_openai_client: MagicMock
    ) -> None:
        """_node_content が str でも dict でもない型 → str() で返す。"""
        service, _ = _build_service(mock_openai_client)
        text = service._extract_text({"_node_content": 12345})
        assert text == "12345"


# ── _generate usage=None ブランチ ────────────────────────────


class TestGenerateUsageNone:
    """response.usage が None の場合のテスト。"""

    def test_generate_usage_none_returns_zero_tokens(
        self, mock_openai_client: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_response.usage = None  # ← usage が None
        mock_openai_client.chat.completions.create.return_value = mock_response

        service, _ = _build_service(mock_openai_client)
        sources = [
            SourceChunk(text="chunk", source_file="f.pdf", score=0.9),
        ]

        result = service._generate("q", sources)

        assert result[0] == "ok"
        assert result[2] == 0  # prompt_tokens
        assert result[3] == 0  # completion_tokens
        assert result[4] == 0  # total_tokens

    def test_generate_none_content_returns_empty_string(
        self, mock_openai_client: MagicMock
    ) -> None:
        """LLM response content が None → 空文字を返す。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15
        mock_response.usage = mock_usage
        mock_openai_client.chat.completions.create.return_value = mock_response

        service, _ = _build_service(mock_openai_client)
        sources = [
            SourceChunk(text="chunk", source_file="f.pdf", score=0.9),
        ]

        result = service._generate("q", sources)

        assert result[0] == ""
        assert result[4] == 15


# ── RagResult dataclass デフォルト値テスト ────────────────────


class TestRagResultDefaults:
    def test_default_metadata_values(self) -> None:
        result = RagResult(answer="test")
        assert result.sources == []
        assert result.latency_ms == 0.0
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0


# ── __init__ バリデーションテスト ────────────────────────────


class TestServiceInitValidation:
    def test_top_k_zero_raises_value_error(
        self, mock_openai_client: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="top_k must be greater than 0"):
            RagService(
                qdrant_wrapper=MagicMock(),
                top_k=0,
            )

    def test_negative_top_k_raises_value_error(
        self, mock_openai_client: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="top_k must be greater than 0"):
            RagService(
                qdrant_wrapper=MagicMock(),
                top_k=-1,
            )

    def test_invalid_retrieval_mode_raises_value_error(
        self, mock_openai_client: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="unsupported retrieval_mode"):
            RagService(
                qdrant_wrapper=MagicMock(),
                retrieval_mode="invalid_mode",
            )


# ── _search limit=None ブランチ ──────────────────────────────


class TestSearchLimitNone:
    def test_search_uses_top_k_when_limit_is_none(
        self, mock_openai_client: MagicMock
    ) -> None:
        service, wrapper = _build_service(mock_openai_client, top_k=3)
        wrapper.client.query_points.return_value = FakeQueryResult(points=[])

        service._search([0.1] * 8, user_roles=["staff"], limit=None)

        call_kwargs = wrapper.client.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 3

    def test_search_uses_explicit_limit(
        self, mock_openai_client: MagicMock
    ) -> None:
        service, wrapper = _build_service(mock_openai_client, top_k=3)
        wrapper.client.query_points.return_value = FakeQueryResult(points=[])

        service._search([0.1] * 8, user_roles=["staff"], limit=10)

        call_kwargs = wrapper.client.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 10


# ── candidate_top_k プロパティ ───────────────────────────────


class TestCandidateTopK:
    def test_candidate_top_k_uses_default_when_small(
        self, mock_openai_client: MagicMock
    ) -> None:
        service, _ = _build_service(mock_openai_client, top_k=3)
        assert service.candidate_top_k == DEFAULT_CANDIDATE_TOP_K

    def test_candidate_top_k_scales_with_large_top_k(
        self, mock_openai_client: MagicMock
    ) -> None:
        service, _ = _build_service(mock_openai_client, top_k=10)
        assert service.candidate_top_k == 40  # 10 * 4

    def test_candidate_top_k_boundary(
        self, mock_openai_client: MagicMock
    ) -> None:
        service, _ = _build_service(mock_openai_client, top_k=5)
        # max(20, 5*4=20) == 20
        assert service.candidate_top_k == DEFAULT_CANDIDATE_TOP_K


# ── _point_to_source_chunk payload=None ──────────────────────


class TestPointToSourceChunk:
    def test_point_with_none_payload(
        self, mock_openai_client: MagicMock
    ) -> None:
        service, _ = _build_service(mock_openai_client)
        point = MagicMock()
        point.payload = None
        point.score = 0.5

        chunk = service._point_to_source_chunk(point)
        assert chunk.text == ""
        assert chunk.source_file == "unknown"
        assert chunk.chunk_index == 0
        assert chunk.payload == {}


# ── ask() メタデータ付き正常系 ───────────────────────────────


class TestAskWithMetadata:
    def test_ask_populates_metadata_fields(
        self, mock_openai_client: MagicMock
    ) -> None:
        """ask() がメタデータ付きの RagResult を返すことを検証。"""
        service, wrapper = _build_service(mock_openai_client)
        wrapper.client.query_points.return_value = FakeQueryResult(
            points=[
                FakePoint(
                    payload={
                        "text": "テスト",
                        "source_file": "t.pdf",
                        "allowed_roles": ["staff"],
                    },
                    score=0.9,
                ),
            ]
        )

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="回答"))]
        mock_response.usage = mock_usage
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = service.ask("質問", user_roles=["staff"])

        assert result.answer == "回答"
        assert result.latency_ms >= 0
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50
        assert result.total_tokens == 150


# ── _rerank_sources エッジケース ──────────────────────────────


class TestRerankEdgeCases:
    """_rerank_sources の全ブランチをカバーする。"""

    def _make_rerank_service(
        self,
        mock_openai_client: MagicMock,
        reranker_client: Any,
        top_k: int = 2,
    ) -> RagService:
        wrapper = MagicMock()
        wrapper.client.query_points.return_value = FakeQueryResult(points=[])
        service = RagService(
            qdrant_wrapper=wrapper,
            retrieval_mode="hybrid_rerank",
            top_k=top_k,
            reranker_client=reranker_client,
        )
        service.openai_client = mock_openai_client
        return service

    def test_empty_sources_returns_empty(
        self, mock_openai_client: MagicMock
    ) -> None:
        """ソースが空 → 空リストを返す。"""
        reranker = MagicMock()
        service = self._make_rerank_service(mock_openai_client, reranker, top_k=2)
        result = service._rerank_sources("q", [])
        assert result == []
        reranker.rerank.assert_not_called()

    def test_reranker_none_returns_truncated(
        self, mock_openai_client: MagicMock
    ) -> None:
        """reranker_client が None → 先頭 top_k 件を返す。"""
        wrapper = MagicMock()
        wrapper.client.query_points.return_value = FakeQueryResult(points=[])
        service = RagService(
            qdrant_wrapper=wrapper,
            retrieval_mode="vector",
            top_k=1,
        )
        service.openai_client = mock_openai_client
        service.reranker_client = None

        sources = [
            SourceChunk(text="a", source_file="a.md", score=0.9),
            SourceChunk(text="b", source_file="b.md", score=0.8),
        ]
        result = service._rerank_sources("q", sources)
        assert len(result) == 1
        assert result[0].text == "a"

    def test_rerank_with_duplicate_indexes(
        self, mock_openai_client: MagicMock
    ) -> None:
        """リランカーが重複インデックスを返す → 重複排除。"""
        reranker = MagicMock()
        reranker.rerank.return_value = [
            RerankResult(index=0),
            RerankResult(index=0),  # duplicate
            RerankResult(index=1),
        ]
        service = self._make_rerank_service(mock_openai_client, reranker, top_k=2)

        sources = [
            SourceChunk(text="a", source_file="a.md", score=0.9),
            SourceChunk(text="b", source_file="b.md", score=0.8),
        ]
        result = service._rerank_sources("q", sources)
        assert len(result) == 2
        assert result[0].text == "a"
        assert result[1].text == "b"

    def test_rerank_with_out_of_range_index(
        self, mock_openai_client: MagicMock
    ) -> None:
        """リランカーが範囲外インデックスを返す → スキップ。"""
        reranker = MagicMock()
        reranker.rerank.return_value = [
            RerankResult(index=99),  # out of range
            RerankResult(index=-1),  # negative
        ]
        service = self._make_rerank_service(mock_openai_client, reranker, top_k=2)

        sources = [
            SourceChunk(text="a", source_file="a.md", score=0.9),
        ]
        # ordered is empty after filtering → fallback to sources[:top_k]
        result = service._rerank_sources("q", sources)
        assert len(result) == 1
        assert result[0].text == "a"

    def test_rerank_backfill_from_unseen_sources(
        self, mock_openai_client: MagicMock
    ) -> None:
        """リランカーが1件だけ返す → 残りを backfill。"""
        reranker = MagicMock()
        reranker.rerank.return_value = [
            RerankResult(index=1),  # only index 1
        ]
        service = self._make_rerank_service(mock_openai_client, reranker, top_k=3)

        sources = [
            SourceChunk(text="a", source_file="a.md", score=0.9),
            SourceChunk(text="b", source_file="b.md", score=0.8),
            SourceChunk(text="c", source_file="c.md", score=0.7),
        ]
        result = service._rerank_sources("q", sources)
        assert len(result) == 3
        # index 1 first (from reranker), then index 0, index 2 (backfill)
        assert result[0].text == "b"
        assert result[1].text == "a"
        assert result[2].text == "c"


# ── _filter_by_score テスト ──────────────────────────────────


class TestFilterByScore:
    """_filter_by_score の全ブランチをカバーする。"""

    def test_threshold_zero_returns_all(
        self, mock_openai_client: MagicMock
    ) -> None:
        """閾値が 0 → フィルタ無効、全件返す。"""
        service, _ = _build_service(mock_openai_client)
        service.score_threshold = 0.0
        sources = [
            SourceChunk(text="low", source_file="l.md", score=0.01),
            SourceChunk(text="high", source_file="h.md", score=0.9),
        ]
        result = service._filter_by_score(sources)
        assert len(result) == 2

    def test_threshold_filters_low_scores(
        self, mock_openai_client: MagicMock
    ) -> None:
        """閾値 0.5 → 低スコアが除外される。"""
        service, _ = _build_service(mock_openai_client)
        service.score_threshold = 0.5
        sources = [
            SourceChunk(text="low", source_file="l.md", score=0.1),
            SourceChunk(text="mid", source_file="m.md", score=0.5),
            SourceChunk(text="high", source_file="h.md", score=0.9),
        ]
        result = service._filter_by_score(sources)
        assert len(result) == 2
        assert result[0].text == "mid"
        assert result[1].text == "high"

    def test_threshold_filters_all(
        self, mock_openai_client: MagicMock
    ) -> None:
        """全チャンクが閾値未満 → 空リスト。"""
        service, _ = _build_service(mock_openai_client)
        service.score_threshold = 0.9
        sources = [
            SourceChunk(text="a", source_file="a.md", score=0.1),
            SourceChunk(text="b", source_file="b.md", score=0.2),
        ]
        result = service._filter_by_score(sources)
        assert result == []

    def test_threshold_keeps_all_when_above(
        self, mock_openai_client: MagicMock
    ) -> None:
        """全チャンクが閾値以上 → ログ出力なしで全件返す。"""
        service, _ = _build_service(mock_openai_client)
        service.score_threshold = 0.1
        sources = [
            SourceChunk(text="a", source_file="a.md", score=0.5),
            SourceChunk(text="b", source_file="b.md", score=0.9),
        ]
        result = service._filter_by_score(sources)
        assert len(result) == 2
