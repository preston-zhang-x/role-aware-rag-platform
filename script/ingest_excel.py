"""
文書解析テスト用 CLI スクリプト。

使い方:
    python script/ingest_excel.py path/to/file.xlsx
    python script/ingest_excel.py path/to/file.pdf

出力:
    - コンソールに Markdown テキストを表示
    - output.md ファイルに保存
"""

import sys
from pathlib import Path

# プロジェクトルートを Python パスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.document_loader import DocumentLoader


def main():
    # ── 引数チェック ──
    if len(sys.argv) < 2:
        print("使い方: python script/ingest_excel.py <ファイルパス>")
        print("例:     python script/ingest_excel.py data/fixtures/sample.xlsx")
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"解析対象: {file_path}")
    print("=" * 60)

    # ── DocumentLoader で解析 ──
    loader = DocumentLoader()

    try:
        result = loader.load(file_path)
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

    # ── Markdown 出力 ──
    print(result.text)

    # ── メタデータ表示 ──
    print("=" * 60)
    print(f"チャンク数: {len(result.chunks)}")
    for i, chunk in enumerate(result.chunks, start=1):
        print(
            f"  [{i}] type={chunk.content_type.value}, "
            f"sheet={chunk.sheet_name}, "
            f"range={chunk.cell_range}"
        )

    # ── 警告表示 ──
    if result.warnings:
        print(f"\n警告 ({len(result.warnings)}件):")
        for w in result.warnings:
            print(f"  - {w}")

    # ── ファイル保存 ──
    output_path = Path("output.md")
    output_path.write_text(result.text, encoding="utf-8")
    print(f"\n保存先: {output_path.resolve()}")


if __name__ == "__main__":
    main()
