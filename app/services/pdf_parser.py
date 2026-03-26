"""
PDF 文書パーサー。
分層パイプラインでテキストとテーブルを抽出し、Markdown に変換する。

Layer 1: テキスト抽出 (pdfplumber)
Layer 2: テーブル抽出 (pdfplumber.extract_tables())
Layer 3: (予約) OCR フォールバック
"""

from pathlib import Path

import pdfplumber

from app.services.base_parser import BaseParser, ParseError
from app.services.parse_result import (
    ChunkMeta,
    ContentType,
    MarkdownEscaper,
    ParseResult,
    ParserWarning,
)


class PDFMarkdownParser(BaseParser):
    """
    PDF → Markdown 変換パーサー。
    """

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == ".pdf"

    def parse(self, file_path: str) -> ParseResult:
        """
        PDF ファイルを解析し、ページごとに Markdown を生成。
        """
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"ファイルが見つかりません: {file_path}", file_path)

        markdown_sections: list[str] = []
        all_chunks: list[ChunkMeta] = []
        all_warnings: list[str] = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # ── ページ見出し注入 ──
                    markdown_sections.append(f"## Page {page_num}\n")

                    # ── Layer 1: テキスト抽出 ──
                    text = page.extract_text()

                    # ── Layer 2: テーブル抽出 ──
                    tables = page.extract_tables()

                    # ── スキャンページ検出 ──
                    is_scan = self._detect_scan_page(text, page)

                    if is_scan:
                        all_warnings.append(
                            f"{ParserWarning.SCAN_PAGE_DETECTED.value}: Page {page_num}"
                        )
                        markdown_sections.append(
                            "_(スキャンページの可能性があります。OCR処理が必要です)_\n"
                        )
                        continue

                    # ── テーブルがある場合 ──
                    if tables:
                        for table_idx, table in enumerate(tables):
                            table_md = self._render_table(table)
                            if table_md:
                                markdown_sections.append(table_md + "\n")
                                all_chunks.append(
                                    ChunkMeta(
                                        source_file=file_path,
                                        content_type=ContentType.TABLE,
                                        page_number=page_num,
                                        cell_range=f"table_{table_idx + 1}",
                                    )
                                )

                    # ── テーブル以外のテキスト ──
                    if text:
                        # テーブル部分はテキストと重複する可能性があるが、
                        # 完全性のためテキストも出力する
                        markdown_sections.append(text + "\n")
                        all_chunks.append(
                            ChunkMeta(
                                source_file=file_path,
                                content_type=ContentType.TEXT,
                                page_number=page_num,
                            )
                        )

        except Exception as e:
            raise ParseError(f"PDF解析に失敗しました: {e}", file_path)

        return ParseResult(
            text="\n".join(markdown_sections),
            chunks=all_chunks,
            warnings=all_warnings,
        )

    # ─── ヘルパーメソッド ───

    def _detect_scan_page(self, text: str | None, page) -> bool:
        """
        スキャンページかどうかを判定。
        テキストがほとんどなく、ページに画像が含まれている場合 → スキャン。
        """
        has_little_text = text is None or len(text.strip()) < 50
        has_images = len(page.images) > 0 if hasattr(page, "images") else False
        return has_little_text and has_images

    def _render_table(self, table: list[list]) -> str:
        """
        pdfplumber が返す2Dリスト(able)を Markdown テーブルに変換。
        """
        if not table or len(table) < 1:
            return ""

        # None を空文字に変換
        clean_table = [
            [str(cell) if cell is not None else "" for cell in row] for row in table
        ]

        headers = clean_table[0]
        data_rows = clean_table[1:] if len(clean_table) > 1 else []

        return MarkdownEscaper.make_table(headers, data_rows)
