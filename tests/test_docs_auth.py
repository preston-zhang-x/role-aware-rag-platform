"""
tests/test_docs_auth.py
───────────────────────
ドキュメント API の認可テスト。
"""

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
) -> None:
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_docs_requires_auth(client: TestClient):
    """Token なしの一覧取得は 401 を返す。"""
    response = client.get("/api/v1/docs/")
    assert response.status_code == 401


def test_staff_cannot_create_doc(client: TestClient, test_db_session: Session):
    """Staff はドキュメントを作成できない。"""
    create_user(test_db_session, "staff1", "password123", UserRole.STAFF)
    token = login(client, "staff1", "password123")

    response = client.post(
        "/api/v1/docs/",
        headers=auth_headers(token),
        json={"title": "blocked", "content": "staff should fail"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_manager_can_create_doc(client: TestClient, test_db_session: Session):
    """Manager はドキュメントを作成できる。"""
    create_user(test_db_session, "manager1", "password123", UserRole.MANAGER)
    token = login(client, "manager1", "password123")

    response = client.post(
        "/api/v1/docs/",
        headers=auth_headers(token),
        json={"title": "allowed", "content": "manager can create"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "allowed"


def test_admin_can_delete_doc(client: TestClient, test_db_session: Session):
    """Admin はドキュメントを削除できる。"""
    create_user(test_db_session, "admin1", "password123", UserRole.ADMIN)
    token = login(client, "admin1", "password123")

    doc = Document(title="to delete", content="content")
    test_db_session.add(doc)
    test_db_session.commit()
    test_db_session.refresh(doc)

    response = client.delete(
        f"/api/v1/docs/{doc.id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 204
