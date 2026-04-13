from fastapi.testclient import TestClient
import pytest
from _pytest import pathlib as pytest_pathlib
from _pytest import tmpdir as pytest_tmpdir
from pathlib import Path
import shutil
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session
import uuid

from app.main import app as fastapi_app
from app.db.base import Base
from app.db.session import get_db


_cleanup_dead_symlinks = pytest_pathlib.cleanup_dead_symlinks
_rm_rf = pytest_pathlib.rm_rf


def _safe_cleanup_dead_symlinks(root) -> None:
    try:
        _cleanup_dead_symlinks(root)
    except PermissionError:
        # Some Windows sandbox environments deny directory enumeration during
        # pytest's tmpdir cleanup even though the tests themselves succeeded.
        return


def _safe_rm_rf(path) -> None:
    try:
        _rm_rf(path)
    except PermissionError:
        return


pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
pytest_pathlib.rm_rf = _safe_rm_rf
pytest_tmpdir.rm_rf = _safe_rm_rf


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parents[1] / ".tmp" / "test-tmp" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    import os

    previous = os.environ.get("LOGURU_ENQUEUE")
    os.environ["LOGURU_ENQUEUE"] = "false"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("LOGURU_ENQUEUE", None)
        else:
            os.environ["LOGURU_ENQUEUE"] = previous


@pytest.fixture(scope="function")
def test_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Use StaticPool to allow multiple connections to the in-memory database
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
        autocommit=False, autoflush=False, bind=test_db_engine
    )

    session = TestingSessionLocal()
    try:
        yield session  # return the session to the test
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
