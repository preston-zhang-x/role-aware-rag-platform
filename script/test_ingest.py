"""
手動テスト: IngestService の動作確認。
python -m script.test_ingest
"""

from app.services.ingest_service import IngestService


def main():
    service = IngestService(collection_name="documents")

    result = service.ingest(
        file_path="data/fixtures/japanese_spec.xlsx",
        allowed_roles=["admin", "staff"],
    )

    print("=" * 50)
    print(f"  入库完了!")
    print(f"  コレクション名: {result.collection_name}")
    print(f"  チャンク数:     {result.total_chunks}")
    print(f"  ソースファイル: {result.source_file}")
    if result.warnings:
        print(f"  警告:")
        for w in result.warnings:
            print(f"    - {w}")
    print("=" * 50)


if __name__ == "__main__":
    main()
