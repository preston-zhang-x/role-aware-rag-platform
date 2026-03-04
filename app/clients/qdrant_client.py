from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

class QdrantSettings(BaseSettings):
    # .env からQdrant接続設定を読み込む
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None

class QdrantClientWrapper:
    def __init__(self, settings: Optional[QdrantSettings] = None):
        # 設定が未指定の場合はデフォルト設定を使う
        self.settings = settings or QdrantSettings()

        self.client = QdrantClient(
            url=self.settings.qdrant_url,
            api_key=self.settings.qdrant_api_key,
        )

    def create_collection(
            self,
            collection_name: str,
            vector_size: int,
            distance: Distance = Distance.COSINE,
    ) -> bool:
        # コレクションがなければ新規作成する
        try:
            collections = self.client.get_collections().collections
            if any(col.name == collection_name for col in collections):
                print(f"Collection '{collection_name}' already exists.")
                return True
            
            self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance,
                ),
            )
            print(f"Collection '{collection_name}' created successfully.")
            return True
        
        except Exception as e:
            print(f"Error creating collection: {e}")
            return False
        
    def collection_exists(self, collection_name: str) -> bool:
        # 指定コレクションの存在有無を返す
        try:
            collection = self.client.get_collections().collections
            return any(col.name == collection_name for col in collection)
        except Exception:
            return False
        
    def delete_collection(self, collection_name: str) -> bool:
        # 指定コレクションを削除する
        try:
            self.client.delete_collection(collection_name=collection_name)
            print(f"Collection '{collection_name}' deleted successfully.")
            return True
        except Exception as e:
            print(f"Error deleting collection: {e}")
            return False

_qdrant_client: Optional[QdrantClientWrapper] = None


def get_qdrant_client() -> QdrantClientWrapper:
    # アプリ全体で使う単一クライアントを返す
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClientWrapper()
    return _qdrant_client
