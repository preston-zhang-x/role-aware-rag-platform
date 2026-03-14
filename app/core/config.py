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


security_settings = SecuritySettings()  # type: ignore
openai_settings = OpenAISettings()  # type: ignore
