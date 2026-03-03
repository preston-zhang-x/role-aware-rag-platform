from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, Optional

class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

qdrant_url = "http://localhost:6333"
qdrant_api_key: Optional[str] = None

class QdrantClientWrapper:
    def __init__(self, settings: Optional[QdrantSettings] = None):
        self.settings = settings or QdrantSettings()

        self.client = QdrantClient(
            url=self.settings.qdrant_url,
            api_key=self.settings.qdrant_api_key,
        )