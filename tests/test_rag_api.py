"""tests/test_rag_api.py

RAG API エンドポイント (/api/v1/rag/ask) のテスト。
RagService を Mock して、API レイヤーだけをテストする。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models.user import User, UserRole
from app.main import app
from app.services.rag_service import RagResult, SourceChunk


# ── Fixture ──────────────────────────────────────────────────


def _fake_user() -> User:
    """テスト用の偽ユーザーを生成する。"""
    user = MagicMock(spec=User)
    user.role = UserRole.STAFF
    user.username = "testuser"
    return user


@pytest.fixture
def authed_client():
    """認証済みの TestClient を返す。"""
    from app.core.deps import get_current_active_user

    app.dependency_overrides[get_current_active_user] = lambda: _fake_user()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ── テストケース ─────────────────────────────────────────────


class TestRagAskEndpoint:
    """POST /api/v1/rag/ask のテスト。"""

    @patch("app.api.v1.rag.RagService")
    def test_happy_path_returns_answer_with_metadata(
        self, mock_service_class: MagicMock, authed_client: TestClient
    ) -> None:
        """正常時: answer, sources, metadata を返す。"""
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance
        mock_instance.ask.return_value = RagResult(
            answer="テスト回答です",
            sources=[
                SourceChunk(
                    text="ソーステキスト",
                    source_file="doc.pdf",
                    score=0.95,
                    chunk_index=0,
                    payload={
                        "sheet_name": "基本設計",
                        "cell_range": "A1:B3",
                        "content_type": "table",
                    },
                ),
            ],
            latency_ms=123.4,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        response = authed_client.post(
            "/api/v1/rag/ask",
            json={"question": "テスト質問"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "テスト回答です"
        assert len(body["sources"]) == 1
        assert body["sources"][0]["source_file"] == "doc.pdf"
        assert body["sources"][0]["score"] == 0.95
        assert body["sources"][0]["chunk_index"] == 0
        assert body["sources"][0]["sheet_name"] == "基本設計"
        assert body["sources"][0]["cell_range"] == "A1:B3"
        assert body["sources"][0]["content_type"] == "table"
        assert body["metadata"]["latency_ms"] == 123.4
        assert body["metadata"]["prompt_tokens"] == 100
        assert body["metadata"]["completion_tokens"] == 50
        assert body["metadata"]["total_tokens"] == 150

        # RagService が正しくインスタンス化・呼び出しされた
        mock_service_class.assert_called_once()
        mock_instance.ask.assert_called_once_with(
            question="テスト質問",
            user_roles=["staff"],
        )

    @patch("app.api.v1.rag.RagService")
    def test_no_sources_returns_empty_list(
        self, mock_service_class: MagicMock, authed_client: TestClient
    ) -> None:
        """ソースなしの場合も正常にレスポンスを返す。"""
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance
        mock_instance.ask.return_value = RagResult(
            answer="ドキュメントに該当する情報が見つかりませんでした。",
            sources=[],
            latency_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )

        response = authed_client.post(
            "/api/v1/rag/ask",
            json={"question": "存在しない内容"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["sources"] == []
        assert body["metadata"]["total_tokens"] == 0

    def test_empty_question_returns_422(self, authed_client: TestClient) -> None:
        """空の質問は 422 バリデーションエラーを返す。"""
        response = authed_client.post(
            "/api/v1/rag/ask",
            json={"question": ""},
        )
        assert response.status_code == 422

    def test_missing_question_returns_422(self, authed_client: TestClient) -> None:
        """質問フィールドなしは 422 バリデーションエラーを返す。"""
        response = authed_client.post(
            "/api/v1/rag/ask",
            json={},
        )
        assert response.status_code == 422

    @patch("app.api.v1.rag.RagService")
    def test_service_error_returns_500(
        self, mock_service_class: MagicMock, authed_client: TestClient
    ) -> None:
        """RagService がエラーを投げた場合は 500 を返す。"""
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance
        mock_instance.ask.side_effect = RuntimeError("テストエラー")

        response = authed_client.post(
            "/api/v1/rag/ask",
            json={"question": "テスト質問"},
        )

        assert response.status_code == 500
        assert "テストエラー" in response.json()["detail"]

    def test_unauthenticated_returns_401(self) -> None:
        """認証なしの場合は 401 を返す。"""
        # dependency_overrides なしで呼ぶ
        app.dependency_overrides.clear()
        with TestClient(app) as c:
            response = c.post(
                "/api/v1/rag/ask",
                json={"question": "テスト質問"},
            )
        assert response.status_code in (401, 403)
