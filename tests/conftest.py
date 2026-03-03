
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session

from app.main import app as fastapi_app
from app.db.base import Base
from app.db.session import get_db


@pytest.fixture(scope="function")
def test_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, # Use StaticPool to allow multiple connections to the in-memory database
    )

    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup after the test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    from sqlalchemy.orm import sessionmaker

    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=test_db_engine)
    
    session = TestingSessionLocal()
    try:
        yield session #return the session to the test
    finally:
        session.close()

@pytest.fixture(scope="function")
def client(test_db_session: Session):
    # Override the get_db dependency to use the test database session
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(fastapi_app) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()
    
