import pytest
from qdrant_client import QdrantClient

from app.clients.qdrant_client import QdrantClientWrapper, QdrantSettings


@pytest.fixture
def qdrant_client():
    # テストは外部の Qdrant サービスに依存せず、ローカルメモリで完結させる
    settings = QdrantSettings(
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
    )
    wrapper = QdrantClientWrapper(settings=settings)
    wrapper.client = QdrantClient(location=":memory:")
    return wrapper


def test_create_collection(qdrant_client: QdrantClientWrapper):
    # コレクション作成と存在確認をテストする
    collection_name = "test_collection"
    vector_size = 128
    

    qdrant_client.delete_collection(collection_name)

    result = qdrant_client.create_collection(
        collection_name=collection_name,
        vector_size=vector_size,
    )
    
    assert result is True, "コレクションの作成に失敗しました"

    exists = qdrant_client.collection_exists(collection_name)
    assert exists is True, "コレクションが存在しません"

    qdrant_client.delete_collection(collection_name)


def test_collection_exists(qdrant_client: QdrantClientWrapper):
    # 存在しないコレクションの判定をテストする
    exists = qdrant_client.collection_exists("non_existent_collection")
    assert exists is False, "存在しないコレクションは True を返すべきではありません"


def test_delete_collection(qdrant_client: QdrantClientWrapper):
    # コレクション削除後に存在しないことを確認する
    collection_name = "temp_collection"
    
    qdrant_client.create_collection(collection_name, vector_size=128)
    
    result = qdrant_client.delete_collection(collection_name)
    assert result is True, "コレクションの削除に失敗しました"
    
    exists = qdrant_client.collection_exists(collection_name)
    assert exists is False, "コレクションは削除されているはずです"
