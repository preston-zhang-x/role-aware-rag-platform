import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.user import User, UserRole


@pytest.fixture
def test_user(test_db_session: Session):
    user = User(
        username="testuser",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.ADMIN,
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


def test_login_success(client: TestClient, test_user: User):
    login_data = {
        "username": "testuser",
        "password": "testpassword123",
    }

    response = client.post(
        "/api/v1/auth/login",
        data=login_data,
    )

    assert response.status_code == 200

    json_response = response.json()
    assert "access_token" in json_response
    assert json_response["token_type"] == "bearer"
    assert json_response["role"] == "admin"
    assert len(json_response["access_token"]) > 0


def test_login_wrong_password(client: TestClient, test_user: User):
    login_data = {
        "username": "testuser",
        "password": "wrongpassword",
    }

    response = client.post("/api/v1/auth/login", data=login_data)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_user_not_found(client: TestClient):
    login_data = {
        "username": "nonexistent",
        "password": "anypassword",
    }

    response = client.post("/api/v1/auth/login", data=login_data)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_me_success(client: TestClient, test_user: User):
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpassword123"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "username": "testuser",
        "role": "admin",
    }
