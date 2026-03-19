"""
生成済みの仕様 Excel を Qdrant に取り込むための簡易スクリプト。

使い方:
    python script/ingest_repo_spec.py
    python script/ingest_repo_spec.py --file docs/role_aware_rag_platform_spec.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ingest_service import IngestService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest spec workbook into Qdrant.")
    parser.add_argument(
        "--file",
        default="docs/role_aware_rag_platform_spec.xlsx",
        help="Path to the Excel file to ingest.",
    )
    parser.add_argument(
        "--collection",
        default="documents",
        help="Qdrant collection name. Defaults to 'documents'.",
    )
    args = parser.parse_args()

    service = IngestService(collection_name=args.collection)
    result = service.ingest(
        file_path=args.file,
        allowed_roles=["admin", "manager", "staff"],
    )

    print("=" * 60)
    print("Ingest done")
    print(f"collection: {result.collection_name}")
    print(f"chunks: {result.total_chunks}")
    print(f"source: {result.source_file}")
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f" - {warning}")
    print("=" * 60)


if __name__ == "__main__":
    main()
