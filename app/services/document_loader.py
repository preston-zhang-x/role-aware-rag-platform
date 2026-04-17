"""
統一文書ローダー。
レジストリ + フォールバックチェーンで、拡張子に基づき
最適なパーサーを選択し、失敗時は自動降格する。
"""

from pathlib import Path

from app.services.base_parser import BaseParser, ParseError
from app.services.excel_parser import JapaneseExcelParser
from app.services.markitdown_fallback import MarkItDownFallback
from app.services.parse_result import ParseResult, ParserWarning
from app.services.pdf_parser import PDFMarkdownParser


class DocumentLoader:
    """
    文書読み込みの統一エントリーポイント。
    """

    def __init__(self):
        """
        デフォルトのパーサーレジストリを初期化。
        """
        self._registry: dict[str, list[type[BaseParser]]] = {
            ".xlsx": [JapaneseExcelParser, MarkItDownFallback],
            ".xlsm": [JapaneseExcelParser, MarkItDownFallback],
            ".xls": [MarkItDownFallback],  # openpyxl 非対応 → 直接フォールバック
            ".xlsb": [MarkItDownFallback],  # openpyxl 非対応 → 直接フォールバック
            ".pdf": [PDFMarkdownParser, MarkItDownFallback],
            ".html": [MarkItDownFallback],
            ".htm": [MarkItDownFallback],
        }

    def register(self, ext: str, parsers: list[type[BaseParser]]) -> None:
        """
        新しい拡張子とパーサーチェーンを登録。
        既存のエントリがあれば上書き。
        """
        self._registry[ext.lower()] = parsers

    def load(self, file_path: str) -> ParseResult:
        """
        ファイルを解析して ParseResult を返す。
        """
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"ファイルが見つかりません: {file_path}", file_path)

        ext = path.suffix.lower()
        parser_chain = self._registry.get(ext)

        if not parser_chain:
            raise ParseError(
                f"サポートされていないファイル形式です: {ext}\n"
                f"対応形式: {', '.join(sorted(self._registry.keys()))}",
                file_path,
            )

        # ── フォールバックチェーン実行 ──
        errors: list[str] = []

        for parser_cls in parser_chain:
            try:
                result = parser_cls().parse(file_path)

                # Primary 以外で成功 → フォールバック使用の警告を追加
                if parser_cls != parser_chain[0]:
                    result.warnings.append(
                        f"{ParserWarning.PARSER_FALLBACK.value}: "
                        f"{parser_chain[0].__name__} → {parser_cls.__name__}"
                    )

                return result

            except (ParseError, Exception) as e:
                errors.append(f"{parser_cls.__name__}: {e}")
                continue  # 次のフォールバックへ

        # 全パーサー失敗
        error_detail = "\n".join(f"  - {err}" for err in errors)
        raise ParseError(
            f"全てのパーサーが失敗しました:\n{error_detail}",
            file_path,
        )

    def get_supported_extensions(self) -> list[str]:
        """サポート拡張子の一覧を返す。"""
        return sorted(self._registry.keys())
