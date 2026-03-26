from collections.abc import Generator
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.session import sessionmaker as SessionFactory

from app.core.config import ENV_FILE


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    database_url: str | None = None

    def require_database_url(self) -> str:
        if not self.database_url:
            raise ValueError("DATABASE_URL is required. Set it in .env")
        return self.database_url


@lru_cache(maxsize=1)
def get_db_settings() -> DBSettings:
    return DBSettings()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_db_settings()
    return create_engine(settings.require_database_url(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> SessionFactory:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
