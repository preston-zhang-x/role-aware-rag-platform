"""認可 API の統合テスト。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.document import Document
from app.db.models.user import User, UserRole


def create_user(
    db: Session,
    username: str,
    password: str,
    role: UserRole,
) -> User:
    """テスト用ユーザーを作成する。"""
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_and_get_token(client: TestClient, username: str, password: str) -> str:
    """ログインして JWT を取得する。"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, f"ログイン失敗: {response.json()}"
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    """Bearer 認証ヘッダーを返す。"""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_token(client: TestClient, test_db_session: Session) -> str:
    """Admin のトークンを返す。"""
    create_user(test_db_session, "admin_test", "admin_pass", UserRole.ADMIN)
    return login_and_get_token(client, "admin_test", "admin_pass")


@pytest.fixture
def manager_token(client: TestClient, test_db_session: Session) -> str:
    """Manager のトークンを返す。"""
    create_user(test_db_session, "manager_test", "mgr_pass", UserRole.MANAGER)
    return login_and_get_token(client, "manager_test", "mgr_pass")


@pytest.fixture
def staff_token(client: TestClient, test_db_session: Session) -> str:
    """Staff のトークンを返す。"""
    create_user(test_db_session, "staff_test", "staff_pass", UserRole.STAFF)
    return login_and_get_token(client, "staff_test", "staff_pass")


@pytest.fixture
def sample_doc(test_db_session: Session) -> Document:
    """テスト用ドキュメントを作成する。"""
    doc = Document(title="テスト文書", content="テスト用コンテンツ")
    test_db_session.add(doc)
    test_db_session.commit()
    test_db_session.refresh(doc)
    return doc


class TestNoToken:
    """未認証時の挙動を確認する。"""

    def test_rag_ask_without_token_returns_401(self, client: TestClient):
        """Token なしの RAG 問い合わせは 401 を返す。"""
        response = client.post(
            "/api/v1/rag/ask",
            json={"question": "テスト質問"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_docs_list_without_token_returns_401(self, client: TestClient):
        """Token なしの文書一覧取得は 401 を返す。"""
        response = client.get("/api/v1/docs/")
        assert response.status_code == 401

    def test_docs_create_without_token_returns_401(self, client: TestClient):
        """Token なしの文書作成は 401 を返す。"""
        response = client.post(
            "/api/v1/docs/",
            json={"title": "test", "content": "test content"},
        )
        assert response.status_code == 401


class TestStaffPermissions:
    """Staff 権限を確認する。"""

    def test_staff_cannot_create_doc(self, client: TestClient, staff_token: str):
        """Staff は文書を作成できない。"""
        response = client.post(
            "/api/v1/docs/",
            headers=auth_headers(staff_token),
            json={"title": "blocked", "content": "staff should fail"},
        )
        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]

    def test_staff_cannot_delete_doc(
        self, client: TestClient, staff_token: str, sample_doc: Document
    ):
        """Staff は文書を削除できない。"""
        response = client.delete(
            f"/api/v1/docs/{sample_doc.id}",
            headers=auth_headers(staff_token),
        )
        assert response.status_code == 403

    def test_staff_can_read_docs(self, client: TestClient, staff_token: str):
        """Staff は文書一覧を参照できる。"""
        response = client.get(
            "/api/v1/docs/",
            headers=auth_headers(staff_token),
        )
        assert response.status_code == 200


class TestManagerPermissions:
    """Manager 権限を確認する。"""

    def test_manager_can_create_doc(self, client: TestClient, manager_token: str):
        """Manager は文書を作成できる。"""
        response = client.post(
            "/api/v1/docs/",
            headers=auth_headers(manager_token),
            json={"title": "manager doc", "content": "manager content"},
        )
        assert response.status_code == 201

    def test_manager_cannot_delete_doc(
        self, client: TestClient, manager_token: str, sample_doc: Document
    ):
        """Manager は文書を削除できない。"""
        response = client.delete(
            f"/api/v1/docs/{sample_doc.id}",
            headers=auth_headers(manager_token),
        )
        assert response.status_code == 403


class TestAdminPermissions:
    """Admin 権限を確認する。"""

    def test_admin_can_create_doc(self, client: TestClient, admin_token: str):
        """Admin は文書を作成できる。"""
        response = client.post(
            "/api/v1/docs/",
            headers=auth_headers(admin_token),
            json={"title": "admin doc", "content": "admin content"},
        )
        assert response.status_code == 201

    def test_admin_can_delete_doc(
        self, client: TestClient, admin_token: str, sample_doc: Document
    ):
        """Admin は文書を削除できる。"""
        response = client.delete(
            f"/api/v1/docs/{sample_doc.id}",
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 204


class TestFriendlyErrors:
    """エラーレスポンスを確認する。"""

    def test_expired_token_returns_401(self, client: TestClient):
        """不正な Token は 401 を返す。"""
        response = client.get(
            "/api/v1/docs/",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

    def test_403_has_clear_message(self, client: TestClient, staff_token: str):
        """403 に権限不足の説明が含まれる。"""
        response = client.post(
            "/api/v1/docs/",
            headers=auth_headers(staff_token),
            json={"title": "test", "content": "test"},
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "permissions" in detail.lower() or "権" in detail
