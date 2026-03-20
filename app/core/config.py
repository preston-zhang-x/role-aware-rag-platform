from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    openai_api_key: str | None = None
    openai_base_url: str
    embedding_model: str
    embedding_dimensions: int
    chat_model: str = "gpt-4o-mini"


class RetrievalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    retrieval_mode: Literal["vector", "bm25", "hybrid", "hybrid_rerank"] = "hybrid"
    top_k: int = Field(default=5, gt=0)
    rerank_base_url: str | None = None
    rerank_api_key: str | None = None
    rerank_model: str | None = None
    rerank_timeout_seconds: float = Field(default=8.0, gt=0)


security_settings = SecuritySettings()  # type: ignore
openai_settings = OpenAISettings()  # type: ignore
retrieval_settings = RetrievalSettings()  # type: ignore
