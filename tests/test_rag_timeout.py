"""tests/test_rag_timeout.py
LLM API の超時・障害時に降格レスポンスを返すことを確認するテスト。
"""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import openai
import pytest
from app.services.rag_service import FALLBACK_ANSWER, RagService, SourceChunk


# ── テスト用 Fixture ──────────────────────────────────────────
@pytest.fixture
def mock_openai_client():
    """OpenAI クライアントの Mock を生成する。"""
    fake_embedding = [0.1] * 8
    with patch("app.services.rag_service.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        # Embedding は正常に動くようにしておく
        embedding_response = MagicMock()
        embedding_response.data = [MagicMock(embedding=fake_embedding)]
        mock_client.embeddings.create.return_value = embedding_response
        yield mock_client


def _build_service_with_sources(
    mock_openai_client: MagicMock,
) -> tuple[RagService, list[SourceChunk]]:
    """テスト用に RagService を構築し、テスト用ソースを返す。"""
    wrapper = MagicMock()
    service = RagService(
        qdrant_wrapper=wrapper,
        retrieval_mode="vector",
    )
    service.openai_client = mock_openai_client
    # テスト用のソースデータ
    sources = [
        SourceChunk(
            text="売上高は前年比10%増加しました。",
            source_file="finance_report.pdf",
            score=0.9,
            chunk_index=0,
        ),
    ]
    return service, sources


# ── テストケース ─────────────────────────────────────────────
class TestLLMTimeoutFallback:
    """LLM API 障害時の降格テスト。"""

    def test_timeout_returns_fallback_answer(
        self, mock_openai_client: MagicMock
    ) -> None:
        """タイムアウト時に降格レスポンスを返す。"""
        # Arrange: LLM 呼び出しでタイムアウトを発生させる
        mock_openai_client.chat.completions.create.side_effect = openai.APITimeoutError(
            request=MagicMock()
        )
        service, sources = _build_service_with_sources(mock_openai_client)
        # Act: _generate を直接呼ぶ
        result = service._generate("売上の概要を教えて", sources)
        # Assert: 降格メッセージが返る & 例外は飛ばない
        assert result[0] == FALLBACK_ANSWER
        assert result == (FALLBACK_ANSWER, 0.0, 0, 0, 0)

    def test_connection_error_returns_fallback_answer(
        self, mock_openai_client: MagicMock
    ) -> None:
        """接続エラー時にも降格レスポンスを返す。"""
        mock_openai_client.chat.completions.create.side_effect = (
            openai.APIConnectionError(request=MagicMock())
        )
        service, sources = _build_service_with_sources(mock_openai_client)
        result = service._generate("売上の概要を教えて", sources)
        assert result[0] == FALLBACK_ANSWER
        assert result == (FALLBACK_ANSWER, 0.0, 0, 0, 0)

    def test_rate_limit_returns_fallback_answer(
        self, mock_openai_client: MagicMock
    ) -> None:
        """レート制限（429）時にも降格レスポンスを返す。"""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_openai_client.chat.completions.create.side_effect = openai.RateLimitError(
            message="rate limit",
            response=mock_response,
            body=None,
        )
        service, sources = _build_service_with_sources(mock_openai_client)
        result = service._generate("売上の概要を教えて", sources)
        assert result[0] == FALLBACK_ANSWER
        assert result == (FALLBACK_ANSWER, 0.0, 0, 0, 0)

    def test_server_error_returns_fallback_answer(
        self, mock_openai_client: MagicMock
    ) -> None:
        """LLM が 500 エラーを返した場合も降格レスポンスを返す。"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_openai_client.chat.completions.create.side_effect = (
            openai.InternalServerError(
                message="internal server error",
                response=mock_response,
                body=None,
            )
        )
        service, sources = _build_service_with_sources(mock_openai_client)
        result = service._generate("売上の概要を教えて", sources)
        assert result[0] == FALLBACK_ANSWER
        assert result == (FALLBACK_ANSWER, 0.0, 0, 0, 0)

    def test_ask_returns_fallback_on_llm_timeout(
        self, mock_openai_client: MagicMock
    ) -> None:
        """ask() のエンドツーエンドで、LLM タイムアウト時に降格レスポンスを返す。
        _generate だけでなく、ask() 全体の流れを検証する。
        """
        from dataclasses import dataclass
        from typing import Any

        @dataclass
        class FakePoint:
            payload: dict[str, Any]
            score: float

        @dataclass
        class FakeQueryResult:
            points: list[FakePoint]

        # Qdrant は正常に動く（検索結果あり）
        wrapper = MagicMock()
        wrapper.client.query_points.return_value = FakeQueryResult(
            points=[
                FakePoint(
                    payload={
                        "text": "テストデータ",
                        "source_file": "test.pdf",
                        "chunk_index": 0,
                        "allowed_roles": ["staff"],
                    },
                    score=0.9,
                )
            ]
        )
        service = RagService(
            qdrant_wrapper=wrapper,
            retrieval_mode="vector",
        )
        service.openai_client = mock_openai_client
        # LLM だけタイムアウト
        mock_openai_client.chat.completions.create.side_effect = openai.APITimeoutError(
            request=MagicMock()
        )
        # Act: ask() を呼ぶ（検索は成功するが LLM がタイムアウト）
        result = service.ask("テスト質問", user_roles=["staff"])
        # Assert: 降格メッセージ + ソースは取得済み + メタデータはゼロ
        assert result.answer == FALLBACK_ANSWER
        assert len(result.sources) == 1
        assert result.sources[0].source_file == "test.pdf"
        assert result.latency_ms == 0.0
        assert result.total_tokens == 0
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
