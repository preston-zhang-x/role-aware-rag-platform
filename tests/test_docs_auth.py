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
    response = client.get("/api/v1/docs/")
    assert response.status_code == 401


def test_viewer_cannot_create_doc(client: TestClient, test_db_session: Session):
    create_user(test_db_session, "viewer1", "password123", UserRole.VIEWER)
    token = login(client, "viewer1", "password123")

    response = client.post(
        "/api/v1/docs/",
        headers=auth_headers(token),
        json={"title": "blocked", "content": "viewer should fail"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_editor_can_create_doc(client: TestClient, test_db_session: Session):
    create_user(test_db_session, "editor1", "password123", UserRole.EDITOR)
    token = login(client, "editor1", "password123")

    response = client.post(
        "/api/v1/docs/",
        headers=auth_headers(token),
        json={"title": "allowed", "content": "editor can create"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "allowed"


def test_admin_can_delete_doc(client: TestClient, test_db_session: Session):
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
