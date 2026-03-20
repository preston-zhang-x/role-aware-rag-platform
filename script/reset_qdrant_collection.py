"""
Qdrant の指定 collection を削除する簡易スクリプト。

使い方:
    python script/reset_qdrant_collection.py
    python script/reset_qdrant_collection.py --collection documents
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.qdrant_client import get_qdrant_client


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete a Qdrant collection.")
    parser.add_argument(
        "--collection",
        default="documents",
        help="Collection name to delete. Defaults to 'documents'.",
    )
    args = parser.parse_args()

    client = get_qdrant_client()
    collection_name = args.collection

    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)
        print(f"Deleted collection: {collection_name}")
        return

    print(f"Collection does not exist: {collection_name}")


if __name__ == "__main__":
    main()
