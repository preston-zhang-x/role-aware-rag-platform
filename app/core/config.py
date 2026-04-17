from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    openai_api_key: str | None = None
    openai_base_url: str
    embedding_model: str
    embedding_dimensions: int
    chat_model: str = "gpt-4o-mini"
    chat_think: bool | None = False


class RetrievalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    retrieval_mode: Literal["vector", "bm25", "hybrid", "hybrid_rerank"] = (
        "hybrid_rerank"
    )
    top_k: int = Field(default=5, gt=0)
    score_threshold: float = Field(default=0.0, ge=0.0)
    rerank_base_url: str | None = None
    rerank_api_key: str | None = None
    rerank_model: str | None = None
    rerank_timeout_seconds: float = Field(default=8.0, gt=0)


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    return SecuritySettings()


@lru_cache(maxsize=1)
def get_openai_settings() -> OpenAISettings:
    return OpenAISettings()


@lru_cache(maxsize=1)
def get_retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings()
