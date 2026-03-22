"""tests/test_rag_role_filter.py

ロールフィルタの単体テスト:
  - Admin は機密チャンクを取得できる
  - Staff は機密チャンクを取得できない（フィルタされる）

テスト戦略:
  Qdrant と OpenAI を Mock して、Filter ロジックだけをテストする。
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag_service import RagService, SourceChunk

# ── テストデータ ──────────────────────────────────────────


@dataclass
class FakePoint:
    payload: dict
    score: float


@dataclass
class FakeQueryResult:
    points: list[FakePoint]


CONFIDENTIAL_POINT = FakePoint(
    payload={
        "text": "Q4 機密財務データ: 売上高が 15% 増加",
        "source_file": "Q4_finance.xlsx",
        "allowed_roles": ["admin", "manager"],
        "chunk_index": 0,
    },
    score=0.95,
)

PUBLIC_POINT = FakePoint(
    payload={
        "text": "社員食堂の今週のメニュー: 月曜日は角煮...",
        "source_file": "lunch_menu.pdf",
        "allowed_roles": ["admin", "manager", "staff"],
        "chunk_index": 0,
    },
    score=0.85,
)


@pytest.fixture
def mock_qdrant():
    """
    Qdrant クライアントの Mock を作成する。
    """
    wrapper = MagicMock()
    return wrapper


@pytest.fixture
def mock_openai_embed():
    fake_embedding = [0.1] * 256

    with patch("app.services.rag_service.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client

        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock(embedding=fake_embedding)]
        mock_client.embeddings.create.return_value = mock_embedding_response

        yield mock_client


def _build_service(mock_qdrant, mock_openai_client) -> RagService:
    service = RagService(qdrant_wrapper=mock_qdrant, retrieval_mode="vector")
    service.openai_client = mock_openai_client
    return service


# ── テストケース ─────────────────────────────────────────


class TestRoleFilter:
    def test_admin_can_search_confidential(self, mock_qdrant, mock_openai_embed):

        mock_qdrant.client.query_points.return_value = FakeQueryResult(
            points=[CONFIDENTIAL_POINT, PUBLIC_POINT]
        )

        service = _build_service(mock_qdrant, mock_openai_embed)
        service._generate = MagicMock(return_value=("これは Admin 向けの回答です", 10.0, 100, 50, 150))
        result = service.ask("財務データ", user_roles=["admin"])

        assert len(result.sources) == 2
        assert result.sources[0].source_file == "Q4_finance.xlsx"
        assert result.answer == "これは Admin 向けの回答です"

        call_args = mock_qdrant.client.query_points.call_args
        query_filter = call_args.kwargs.get("query_filter") or call_args[1].get(
            "query_filter"
        )

        assert query_filter is not None
        must_conditions = query_filter.must
        assert len(must_conditions) == 1
        assert must_conditions[0].key == "allowed_roles"

    def test_staff_cannot_search_confidential(self, mock_qdrant, mock_openai_embed):
        mock_qdrant.client.query_points.return_value = FakeQueryResult(
            points=[PUBLIC_POINT]
        )

        service = _build_service(mock_qdrant, mock_openai_embed)
        service._generate = MagicMock(return_value=("これは Staff 向けの回答です", 5.0, 80, 30, 110))

        result = service.ask("財務データ", user_roles=["staff"])

        assert len(result.sources) == 1
        assert result.sources[0].source_file == "lunch_menu.pdf"

        call_args = mock_qdrant.client.query_points.call_args
        query_filter = call_args.kwargs.get("query_filter") or call_args[1].get(
            "query_filter"
        )
        assert query_filter is not None

    def test_no_results_returns_default_message(self, mock_qdrant, mock_openai_embed):
        mock_qdrant.client.query_points.return_value = FakeQueryResult(points=[])

        service = _build_service(mock_qdrant, mock_openai_embed)

        # Act
        result = service.ask("存在しない内容", user_roles=["staff"])

        assert "見つかりませんでした" in result.answer
        assert len(result.sources) == 0

    def test_search_reads_text_from_node_content_json(
        self, mock_qdrant, mock_openai_embed
    ):
        mock_qdrant.client.query_points.return_value = FakeQueryResult(
            points=[
                FakePoint(
                    payload={
                        "_node_content": '{"text": "ノード内部の本文です"}',
                        "allowed_roles": ["staff"],
                    },
                    score=0.77,
                )
            ]
        )

        service = _build_service(mock_qdrant, mock_openai_embed)

        sources = service._search([0.1] * 256, user_roles=["staff"])

        assert len(sources) == 1
        assert sources[0].text == "ノード内部の本文です"
        assert sources[0].source_file == "unknown"
        assert sources[0].chunk_index == 0

    def test_search_falls_back_to_string_when_node_content_is_invalid(
        self, mock_qdrant, mock_openai_embed
    ):
        mock_qdrant.client.query_points.return_value = FakeQueryResult(
            points=[
                FakePoint(
                    payload={
                        "_node_content": "{invalid json}",
                        "source_file": "broken.txt",
                        "chunk_index": 2,
                        "allowed_roles": ["staff"],
                    },
                    score=0.64,
                )
            ]
        )

        service = _build_service(mock_qdrant, mock_openai_embed)

        sources = service._search([0.1] * 256, user_roles=["staff"])

        assert len(sources) == 1
        assert sources[0].text == "{invalid json}"
        assert sources[0].source_file == "broken.txt"
        assert sources[0].chunk_index == 2

    def test_generate_builds_context_and_returns_llm_message(
        self, mock_qdrant, mock_openai_embed
    ):
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 200
        mock_usage.completion_tokens = 80
        mock_usage.total_tokens = 280

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="出典付きの回答です"))
        ]
        mock_response.usage = mock_usage
        mock_openai_embed.chat.completions.create.return_value = mock_response

        service = _build_service(mock_qdrant, mock_openai_embed)
        sources = [
            SourceChunk(
                text="売上高は前四半期比で増加しました。",
                source_file="finance_report.pdf",
                score=0.9,
                chunk_index=0,
            ),
            SourceChunk(
                text="詳細は付録を参照してください。",
                source_file="appendix.md",
                score=0.8,
                chunk_index=1,
            ),
        ]

        result = service._generate("売上の要点を教えてください", sources)

        assert result[0] == "出典付きの回答です"
        assert result[1] >= 0  # latency_ms >= 0 (mock call is near-instant)
        assert result[2] == 200  # prompt_tokens
        assert result[3] == 80   # completion_tokens
        assert result[4] == 280  # total_tokens

        call_args = mock_openai_embed.chat.completions.create.call_args
        assert call_args.kwargs["model"]
        assert call_args.kwargs["temperature"] == 0.3
        assert call_args.kwargs["messages"][0]["role"] == "system"
        assert "finance_report.pdf" in call_args.kwargs["messages"][1]["content"]
        assert "appendix.md" in call_args.kwargs["messages"][1]["content"]
        assert "売上の要点を教えてください" in call_args.kwargs["messages"][1]["content"]
