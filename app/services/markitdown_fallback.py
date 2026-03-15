"""
MarkItDown フォールバックパーサー。
プライマリパーサーが失敗した際の最終防衛線。
"""

from pathlib import Path

from markitdown import MarkItDown

from app.services.base_parser import BaseParser, ParseError
from app.services.parse_result import (
    ChunkMeta,
    ContentType,
    ParseResult,
    ParserWarning,
)


class MarkItDownFallback(BaseParser):
    # サポートする拡張子一覧
    SUPPORTED_EXTENSIONS = {
        ".xlsx",
        ".xls",
        ".xlsm",
        ".xlsb",
        ".pdf",
        ".docx",
        ".doc",
        ".pptx",
        ".ppt",
        ".csv",
        ".tsv",
        ".html",
        ".htm",
    }

    def can_handle(self, file_path: str) -> bool:
        suffix = Path(file_path).suffix.lower()
        return suffix in self.SUPPORTED_EXTENSIONS

    def parse(self, file_path: str) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"ファイルが見つかりません: {file_path}", file_path)

        try:
            converter = MarkItDown()
            result = converter.convert(str(path))
            text = result.text_content or ""
        except Exception as e:
            raise ParseError(f"MarkItDown フォールバックも失敗しました: {e}", file_path)

        return ParseResult(
            text=text,
            chunks=[
                ChunkMeta(
                    source_file=file_path,
                    content_type=ContentType.TEXT,
                )
            ],
            warnings=[
                f"{ParserWarning.PARSER_FALLBACK.value}: "
                f"MarkItDown による汎用変換を使用しました"
            ],
        )
