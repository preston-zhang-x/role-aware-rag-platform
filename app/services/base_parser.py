"""
全パーサーの抽象基底クラス。
"""

from abc import ABC, abstractmethod

from app.services.parse_result import ParseResult


class BaseParser(ABC):
    """
    全ての文書パーサーが実装すべき統一インターフェース。
    """

    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """
        ファイルを解析し、Markdown テキスト + メタデータを返す。
        """
        ...

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """
        このパーサーが指定ファイルを処理できるか判定。
        """
        ...


class ParseError(Exception):
    """
    パーサー処理中のエラー。
    """

    def __init__(self, message: str, source_file: str | None = None):
        self.source_file = source_file
        super().__init__(message)
