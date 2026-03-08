"""
文档解析结果のデータモデル。
全てのパーサーが統一された ParseResult を返す。
"""

from dataclasses import dataclass, field
from enum import Enum


class ContentType(Enum):
    """解析ブロックの内容タイプ"""

    TABLE = "table"
    KEY_VALUE = "key_value"
    TEXT = "text"
    SHAPE = "shape"


class ParserWarning(Enum):
    """解析中に発生した警告タイプ"""

    FORMULA_NO_CACHE = "数式のキャッシュ値がありません。元の数式を保持します"
    SHAPE_SKIPPED = "図形オブジェクトの完全な抽出はサポートされていません"
    MERGED_CELL_BROADCAST = "結合セルの値をブロードキャスト展開しました"
    HIDDEN_SHEET_SKIPPED = "非表示シートをスキップしました"
    SCAN_PAGE_DETECTED = "スキャンページが検出されました。OCRが必要な可能性があります"
    PARSER_FALLBACK = "プライマリパーサーが失敗し、フォールバックを使用しました"


@dataclass
class ChunkMeta:
    """
    各解析ブロックのメタデータ。
    Qdrant の Payload に書き込まれ、検索時のソースト追跡に使用。
    """

    source_file: str
    content_type: ContentType
    sheet_name: str | None = None  # Excel 専用
    page_number: int | None = None  # PDF 専用
    cell_range: str | None = None  # 例: "A1:F20"
    merged_ranges: list[str] = field(default_factory=list)
    is_broadcast_fill: bool = False  # 広播填充フラグ（token膨張を識別）


@dataclass
class ParseResult:
    """
    全パーサー統一の戻り値型。
    """

    text: str
    chunks: list[ChunkMeta] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MarkdownEscaper:
    """
    Markdown テーブル内の特殊文字をエスケープするユーティリティ。
    """

    @staticmethod
    def escape_cell(text: str) -> str:
        """
        テーブルセル内のテキストをエスケープ。
        | → \\|, 改行 → <br>, 全角スペース → 半角
        """
        if text is None:
            return ""
        text = str(text)
        text = text.replace("|", "\\|")  # パイプ文字はテーブルを破壊する
        text = text.replace("\n", "<br>")  # 改行はテーブル行を破壊する
        text = text.replace("\r", "")  # CR を除去
        text = text.replace("\u3000", " ")  # 全角スペース → 半角
        return text.strip()

    @staticmethod
    def make_table(headers: list[str], rows: list[list[str]]) -> str:
        """
        ヘッダーとデータ行から Markdown テーブルを生成。
        """
        if not headers:
            return ""

        # ヘッダー行
        escaped_headers = [MarkdownEscaper.escape_cell(h) for h in headers]
        header_line = "| " + " | ".join(escaped_headers) + " |"

        # セパレータ行
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"

        # データ行
        data_lines = []
        for row in rows:
            # 列数をヘッダーに合わせる（不足は空文字で埋める）
            padded = row + [""] * (len(headers) - len(row))
            escaped = [
                MarkdownEscaper.escape_cell(cell) for cell in padded[: len(headers)]
            ]
            data_lines.append("| " + " | ".join(escaped) + " |")

        return "\n".join([header_line, separator] + data_lines)
