from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from contextlib import ExitStack
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


BOOTSTRAP_PACKAGES = ("openpyxl",)
SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}


def ensure_dependencies() -> None:
    missing = [
        pkg for pkg in BOOTSTRAP_PACKAGES if importlib.util.find_spec(pkg) is None
    ]
    if not missing:
        return
    print(f"[bootstrap] installing: {', '.join(missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


ensure_dependencies()

import openpyxl  # noqa: E402
from openpyxl.cell.cell import Cell, MergedCell  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.worksheet import Worksheet  # noqa: E402


class ContentType(Enum):
    TABLE = "table"
    KEY_VALUE = "key_value"
    TEXT = "text"
    SHAPE = "shape"


class ParserWarning(Enum):
    FORMULA_NO_CACHE = "数式のキャッシュ値がありません。元の数式を保持します"
    SHAPE_SKIPPED = "図形オブジェクトの完全な抽出はサポートされていません"
    MERGED_CELL_BROADCAST = "結合セルの値をブロードキャスト展開しました"
    HIDDEN_SHEET_SKIPPED = "非表示シートをスキップしました"
    SCAN_PAGE_DETECTED = "スキャンページが検出されました。OCRが必要な可能性があります"
    PARSER_FALLBACK = "プライマリパーサーが失敗し、フォールバックを使用しました"


@dataclass
class ChunkMeta:
    source_file: str
    content_type: ContentType
    sheet_name: str | None = None
    page_number: int | None = None
    cell_range: str | None = None
    merged_ranges: list[str] = field(default_factory=list)
    is_broadcast_fill: bool = False
    char_start: int = 0
    char_end: int = 0


@dataclass
class ParseResult:
    text: str
    chunks: list[ChunkMeta] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MarkdownEscaper:
    @staticmethod
    def escape_cell(text: object | None) -> str:
        if text is None:
            return ""
        text = str(text)
        text = text.replace("|", "\\|")
        text = text.replace("\n", "<br>")
        text = text.replace("\r", "")
        text = text.replace("\u3000", " ")
        return text.strip()

    @staticmethod
    def make_table(headers: list[str], rows: list[list[str]]) -> str:
        if not headers:
            return ""
        escaped_headers = [MarkdownEscaper.escape_cell(h) for h in headers]
        header_line = "| " + " | ".join(escaped_headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        data_lines = []
        for row in rows:
            padded = row + [""] * (len(headers) - len(row))
            escaped = [
                MarkdownEscaper.escape_cell(cell) for cell in padded[: len(headers)]
            ]
            data_lines.append("| " + " | ".join(escaped) + " |")
        return "\n".join([header_line, separator] + data_lines)


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        ...

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        ...


class ParseError(Exception):
    def __init__(self, message: str, source_file: str | None = None):
        self.source_file = source_file
        super().__init__(message)


CellLike = Cell | MergedCell


@dataclass(frozen=True)
class RowCell:
    text: str
    start_col: int
    end_col: int

    @property
    def col_span(self) -> int:
        return self.end_col - self.start_col + 1


@dataclass(frozen=True)
class RowProfile:
    row_index: int
    raw_row: tuple[str, ...]
    cells: tuple[RowCell, ...]


class JapaneseExcelParser(BaseParser):
    MAX_HEADING_LENGTH = 48
    MIN_TABLE_ROWS = 2
    MAX_FORM_ROW_CELLS = 10
    MIN_HEADING_LENGTH = 2
    REPEATED_WIDE_LABEL_MIN_SPAN = 4
    MIN_SHARED_TABLE_COLUMNS = 3
    TWO_ROW_TABLE_SHARED_DENSITY = 0.9
    MIN_STRUCTURED_MERGED_COLUMNS = 4
    LEADING_CONTEXT_MIN_CELLS = 5
    LEADING_CONTEXT_MIN_SPAN = 3
    MAX_KV_KEY_COL_SPAN = 2
    KV_LABEL_TRAILING_CHARS = ":："
    NON_HEADING_PREFIXES = ("->", "→", "=>")
    NON_HEADING_EXACT_TEXTS = {
        "with_payload=True",
        "with_vectors=False",
        "source_file",
        "source_key",
        "allowed_roles",
        "chunk_index",
    }
    NOISE_HEADING_PATTERN = re.compile(r"^[\s()\[\]{}0-9０-９.．-]+$")

    def __init__(self, density_threshold: float = 0.5):
        self.density_threshold = density_threshold

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in {".xlsx", ".xlsm"}

    def parse(self, file_path: str) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"ファイルが見つかりません: {file_path}", file_path)

        all_chunks: list[ChunkMeta] = []
        all_warnings: list[str] = []
        full_text = ""

        with ExitStack() as stack:
            try:
                wb_cached = openpyxl.load_workbook(file_path, data_only=True)
                stack.callback(wb_cached.close)
                wb_formula = openpyxl.load_workbook(file_path, data_only=False)
                stack.callback(wb_formula.close)
            except Exception as exc:
                raise ParseError(f"Excelファイルの読み込みに失敗: {exc}", file_path)

            for sheet_name in wb_cached.sheetnames:
                ws_cached = wb_cached[sheet_name]
                ws_formula = wb_formula[sheet_name]

                if ws_cached.sheet_state != "visible":
                    all_warnings.append(
                        f"{ParserWarning.HIDDEN_SHEET_SKIPPED.value}: {sheet_name}"
                    )
                    continue

                full_text, _ = self._append_section(full_text, f"# {sheet_name}")

                section_md, section_chunks, comments_md = self._parse_visible_sheet(
                    ws_cached,
                    ws_formula,
                    file_path,
                    sheet_name,
                    all_warnings,
                )
                if section_md:
                    full_text, section_start = self._append_section(full_text, section_md)
                    if section_start is not None:
                        for chunk in section_chunks:
                            chunk.char_start += section_start
                            chunk.char_end += section_start
                all_chunks.extend(section_chunks)

                if comments_md:
                    full_text, _ = self._append_section(full_text, comments_md)

        text = full_text + "\n" if full_text else ""
        return ParseResult(text=text, chunks=all_chunks, warnings=all_warnings)

    def _parse_visible_sheet(
        self,
        ws_cached: Worksheet,
        ws_formula: Worksheet,
        file_path: str,
        sheet_name: str,
        warnings: list[str],
    ) -> tuple[str, list[ChunkMeta], str]:
        grid, merge_spans = self._build_grid_with_merged_cells(
            ws_cached,
            ws_formula,
            warnings,
        )
        if not grid:
            return "_(空のシート)_", [], ""

        section_md, section_chunks = self._heuristic_scan(
            grid,
            file_path,
            sheet_name,
            merge_spans,
        )
        return section_md, section_chunks, self._extract_comments(ws_cached)

    def _append_section(self, full_text: str, section: str) -> tuple[str, int | None]:
        normalized = section.strip()
        if not normalized:
            return full_text, None

        separator = "\n\n" if full_text else ""
        start = len(full_text) + len(separator)
        return f"{full_text}{separator}{normalized}", start

    def _build_chunk_meta(
        self,
        file_path: str,
        content_type: ContentType,
        sheet_name: str | None = None,
        cell_range: str | None = None,
        is_broadcast_fill: bool = False,
    ) -> ChunkMeta:
        return ChunkMeta(
            source_file=file_path,
            content_type=content_type,
            sheet_name=sheet_name,
            cell_range=cell_range,
            is_broadcast_fill=is_broadcast_fill,
        )

    def _build_grid_with_merged_cells(
        self,
        ws_cached: Worksheet,
        ws_formula: Worksheet,
        warnings: list[str],
    ) -> tuple[list[list[str]], dict[tuple[int, int], tuple[int, int]]]:
        if ws_cached.max_row is None or ws_cached.max_column is None:
            return [], {}

        max_row = ws_cached.max_row
        max_col = ws_cached.max_column
        grid: list[list[str]] = [["" for _ in range(max_col)] for _ in range(max_row)]

        cached_rows = ws_cached.iter_rows(
            min_row=1,
            max_row=max_row,
            min_col=1,
            max_col=max_col,
        )
        formula_rows = ws_formula.iter_rows(
            min_row=1,
            max_row=max_row,
            min_col=1,
            max_col=max_col,
        )
        for row_idx, (cached_row, formula_row) in enumerate(
            zip(cached_rows, formula_rows, strict=True)
        ):
            for col_idx, (cached_cell, formula_cell) in enumerate(
                zip(cached_row, formula_row, strict=True)
            ):
                grid[row_idx][col_idx] = self._read_cell_value(
                    cached_cell,
                    formula_cell,
                    warnings,
                )

        merge_spans: dict[tuple[int, int], tuple[int, int]] = {}
        for merged_range in ws_cached.merged_cells.ranges:
            anchor = (merged_range.min_row - 1, merged_range.min_col - 1)
            merge_spans[anchor] = (
                merged_range.max_row - merged_range.min_row + 1,
                merged_range.max_col - merged_range.min_col + 1,
            )
            for row_idx in range(merged_range.min_row, merged_range.max_row + 1):
                for col_idx in range(merged_range.min_col, merged_range.max_col + 1):
                    if (row_idx - 1, col_idx - 1) != anchor:
                        grid[row_idx - 1][col_idx - 1] = ""

            warnings.append(f"{ParserWarning.MERGED_CELL_BROADCAST.value}: {merged_range}")

        return grid, merge_spans

    def _read_cell_value(
        self,
        cached_cell: CellLike,
        formula_cell: CellLike,
        warnings: list[str],
    ) -> str:
        cached_value = cached_cell.value
        formula_value = formula_cell.value

        if cached_value is not None:
            return str(cached_value)

        if formula_value is not None and str(formula_value).startswith("="):
            warnings.append(f"{ParserWarning.FORMULA_NO_CACHE.value}: {formula_value}")
            return f"formula: {formula_value}"

        return ""

    def _heuristic_scan(
        self,
        grid: list[list[str]],
        file_path: str,
        sheet_name: str,
        merge_spans: dict[tuple[int, int], tuple[int, int]],
    ) -> tuple[str, list[ChunkMeta]]:
        effective_cols = self._calc_effective_cols(grid)
        if effective_cols == 0:
            return "", []

        row_profiles = [
            self._build_row_profile(row_idx, row[:effective_cols], merge_spans)
            for row_idx, row in enumerate(grid)
        ]

        markdown_parts: list[str] = []
        chunks: list[ChunkMeta] = []
        last_text_block: str | None = None
        index = 0

        while index < len(row_profiles):
            row = row_profiles[index]
            if not row.cells:
                index += 1
                continue

            if len(row.cells) == 1:
                block = self._render_text_row(row, file_path, sheet_name, last_text_block)
                if block is not None:
                    markdown_parts.append(block[0])
                    chunks.append(block[1])
                    last_text_block = block[2]
                index += 1
                continue

            table_len = self._detect_table_length(row_profiles[index:])
            if table_len:
                table_rows = row_profiles[index : index + table_len]
                table_md, chunk = self._render_table_block(table_rows, file_path, sheet_name)
                if table_md:
                    markdown_parts.append(table_md)
                    chunks.append(chunk)
                last_text_block = None
                index += table_len
                continue

            form_md, chunk = self._render_form_row(
                row,
                row_profiles[index + 1] if index + 1 < len(row_profiles) else None,
                file_path,
                sheet_name,
            )
            if form_md:
                markdown_parts.append(form_md)
                chunks.append(chunk)
            last_text_block = None
            index += 1

        return self._with_chunk_positions(markdown_parts, chunks), chunks

    def _with_chunk_positions(
        self,
        markdown_parts: list[str],
        chunks: list[ChunkMeta],
    ) -> str:
        section_text = ""
        for markdown, chunk in zip(markdown_parts, chunks, strict=False):
            if section_text:
                section_text += "\n\n"
            chunk.char_start = len(section_text)
            section_text += markdown
            chunk.char_end = len(section_text)
        return section_text

    def _build_row_profile(
        self,
        row_idx: int,
        row: list[str],
        merge_spans: dict[tuple[int, int], tuple[int, int]],
    ) -> RowProfile:
        cells: list[RowCell] = []
        for col_idx, raw_value in enumerate(row):
            value = MarkdownEscaper.escape_cell(raw_value)
            if not value:
                continue
            _, col_span = merge_spans.get((row_idx, col_idx), (1, 1))
            cell = RowCell(
                text=value,
                start_col=col_idx,
                end_col=col_idx + col_span - 1,
            )
            cells.append(cell)
        return RowProfile(row_index=row_idx, raw_row=tuple(row), cells=tuple(cells))

    def _detect_table_length(self, rows: list[RowProfile]) -> int:
        if len(rows) < self.MIN_TABLE_ROWS:
            return 0

        max_length = 0
        for end in range(self.MIN_TABLE_ROWS, len(rows) + 1):
            candidate = rows[:end]
            if self._looks_like_table_block(candidate):
                max_length = end
                continue
            if max_length:
                break
        return max_length

    def _looks_like_table_block(self, rows: list[RowProfile]) -> bool:
        if len(rows) < self.MIN_TABLE_ROWS:
            return False
        if any(len(row.cells) < 2 for row in rows):
            return False

        first_cells = [row.cells[0] for row in rows[:2]]
        if (
            len(first_cells) == 2
            and first_cells[0].text == first_cells[1].text
            and first_cells[0].col_span >= self.REPEATED_WIDE_LABEL_MIN_SPAN
        ):
            return False

        if self._has_structured_merged_columns(rows):
            return True

        column_sets = [
            {cell.start_col for cell in row.cells} for row in rows[: min(3, len(rows))]
        ]
        shared_columns = set.intersection(*column_sets)
        average_width = sum(len(row.cells) for row in rows) / len(rows)

        if not shared_columns:
            return False

        shared_span = max(shared_columns) - min(shared_columns) + 1
        shared_density = len(shared_columns) / shared_span if shared_span else 0

        if len(rows) == 2:
            return (
                len(shared_columns) >= self.MIN_SHARED_TABLE_COLUMNS
                and shared_density >= self.TWO_ROW_TABLE_SHARED_DENSITY
            )

        return (
            len(shared_columns) >= self.MIN_SHARED_TABLE_COLUMNS
            and average_width >= self.MIN_SHARED_TABLE_COLUMNS
        )

    def _has_structured_merged_columns(self, rows: list[RowProfile]) -> bool:
        sample_rows = rows[: min(3, len(rows))]
        if len(sample_rows) < 2:
            return False

        if min(len(row.cells) for row in sample_rows) < self.MIN_STRUCTURED_MERGED_COLUMNS:
            return False

        if not any(cell.col_span > 1 for row in sample_rows for cell in row.cells):
            return False

        if self._looks_like_merged_kv_pairs(sample_rows):
            return False

        header_positions = tuple(cell.start_col for cell in sample_rows[0].cells)
        if len(header_positions) < self.MIN_STRUCTURED_MERGED_COLUMNS:
            return False

        return all(
            tuple(cell.start_col for cell in row.cells) == header_positions
            for row in sample_rows[1:]
        )

    def _looks_like_merged_kv_pairs(self, rows: list[RowProfile]) -> bool:
        if not rows:
            return False

        cell_count = len(rows[0].cells)
        if (
            cell_count < 4
            or cell_count % 2 != 0
            or cell_count > self.MAX_FORM_ROW_CELLS
        ):
            return False

        reference_positions = tuple(cell.start_col for cell in rows[0].cells)
        if any(
            tuple(cell.start_col for cell in row.cells) != reference_positions
            for row in rows
        ):
            return False

        for row in rows:
            for index in range(0, len(row.cells), 2):
                key_cell = row.cells[index]
                value_cell = row.cells[index + 1]
                if key_cell.col_span > self.MAX_KV_KEY_COL_SPAN:
                    return False
                if value_cell.col_span <= key_cell.col_span:
                    return False

        return True

    def _render_text_row(
        self,
        row: RowProfile,
        file_path: str,
        sheet_name: str,
        last_text_block: str | None,
    ) -> tuple[str, ChunkMeta, str] | None:
        text = row.cells[0].text
        if self._should_skip_text_block(text, last_text_block):
            return None

        markdown = self._render_text_block(text)
        if not markdown:
            return None

        chunk = self._build_chunk_meta(
            file_path=file_path,
            content_type=ContentType.TEXT,
            sheet_name=sheet_name,
            cell_range=f"row {row.row_index + 1}",
            is_broadcast_fill=row.cells[0].col_span > 1,
        )
        return markdown, chunk, text

    def _should_skip_text_block(
        self,
        text: str,
        last_text_block: str | None,
    ) -> bool:
        if text == last_text_block:
            return True
        if self.NOISE_HEADING_PATTERN.fullmatch(text):
            return True
        return False

    def _looks_like_heading(self, text: str) -> bool:
        normalized = text.strip()
        if (
            len(normalized) < self.MIN_HEADING_LENGTH
            or len(normalized) > self.MAX_HEADING_LENGTH
        ):
            return False
        if self.NOISE_HEADING_PATTERN.fullmatch(normalized):
            return False
        if normalized in self.NON_HEADING_EXACT_TEXTS:
            return False
        if normalized.startswith(self.NON_HEADING_PREFIXES):
            return False
        if any(token in normalized for token in ("。", "<br>", r"\|", ":", "：")):
            return False
        return True

    def _render_text_block(self, text: str) -> str:
        if self._looks_like_heading(text):
            return f"## {text}"
        return text

    def _render_form_row(
        self,
        row: RowProfile,
        next_row: RowProfile | None,
        file_path: str,
        sheet_name: str,
    ) -> tuple[str, ChunkMeta]:
        values = [cell.text for cell in row.cells]
        if self._should_drop_leading_context(row, next_row):
            values = values[1:]

        parts: list[str] = []
        i = 0
        while i < len(values):
            if i + 1 < len(values):
                label = self._clean_kv_label(values[i])
                parts.append(f"- **{label}:** {values[i + 1]}")
                i += 2
                continue
            parts.append(f"- {values[i]}")
            i += 1

        chunk = self._build_chunk_meta(
            file_path=file_path,
            content_type=ContentType.KEY_VALUE,
            sheet_name=sheet_name,
            cell_range=f"row {row.row_index + 1}",
        )
        return "\n".join(parts), chunk

    def _clean_kv_label(self, label: str) -> str:
        cleaned = label.strip().rstrip(self.KV_LABEL_TRAILING_CHARS).strip()
        return cleaned or label

    def _should_drop_leading_context(
        self,
        row: RowProfile,
        next_row: RowProfile | None,
    ) -> bool:
        if len(row.cells) < self.LEADING_CONTEXT_MIN_CELLS or len(row.cells) % 2 == 0:
            return False

        first = row.cells[0]
        if first.col_span < self.LEADING_CONTEXT_MIN_SPAN:
            return False

        if next_row and next_row.cells and next_row.cells[0].text == first.text:
            return True

        return first.col_span >= max(cell.col_span for cell in row.cells[1:])

    def _calc_effective_cols(self, grid: list[list[str]]) -> int:
        if not grid:
            return 0
        max_col = len(grid[0])
        for col_idx in range(max_col - 1, -1, -1):
            if any(grid[row_idx][col_idx] != "" for row_idx in range(len(grid))):
                return col_idx + 1
        return 0

    def _render_table_block(
        self,
        rows: list[RowProfile],
        file_path: str,
        sheet_name: str,
    ) -> tuple[str, ChunkMeta]:
        if not rows:
            return "", self._build_chunk_meta(file_path, ContentType.TABLE)

        active_columns = sorted({cell.start_col for row in rows for cell in row.cells})
        if not active_columns:
            return "", self._build_chunk_meta(file_path, ContentType.TABLE)

        compressed_rows = [
            [row.raw_row[col_idx] for col_idx in active_columns] for row in rows
        ]
        deduped_rows = self._dedupe_consecutive_rows(compressed_rows)
        if not deduped_rows:
            return "", self._build_chunk_meta(file_path, ContentType.TABLE)

        headers = deduped_rows[0]
        data_rows = deduped_rows[1:]
        markdown = MarkdownEscaper.make_table(headers, data_rows)

        col_start = get_column_letter(active_columns[0] + 1)
        col_end = get_column_letter(active_columns[-1] + 1)
        cell_range = (
            f"{col_start}{rows[0].row_index + 1}:{col_end}{rows[-1].row_index + 1}"
        )
        chunk = self._build_chunk_meta(
            file_path=file_path,
            content_type=ContentType.TABLE,
            sheet_name=sheet_name,
            cell_range=cell_range,
        )
        return markdown, chunk

    def _dedupe_consecutive_rows(self, rows: list[list[str]]) -> list[list[str]]:
        deduped: list[list[str]] = []
        previous_key: tuple[str, ...] | None = None
        for row in rows:
            normalized_key = tuple(MarkdownEscaper.escape_cell(cell) for cell in row)
            if all(cell == "" for cell in normalized_key):
                continue
            if normalized_key == previous_key:
                continue
            deduped.append(row)
            previous_key = normalized_key
        return deduped

    def _extract_comments(self, ws: Worksheet) -> str:
        comments_md: list[str] = []
        for row in ws.iter_rows():
            for cell in row:
                if not cell.comment:
                    continue
                column_index = cell.column
                if column_index is None:
                    continue
                coord = f"{get_column_letter(column_index)}{cell.row}"
                comment_text = MarkdownEscaper.escape_cell(cell.comment.text)
                comments_md.append(f"- **[{coord}]** {comment_text}")

        if not comments_md:
            return ""
        return "### コメント・注記\n\n" + "\n".join(comments_md)


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def iter_targets(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Not a file or directory: {path}")

    walker = path.rglob("*") if recursive else path.iterdir()
    return sorted(
        item
        for item in walker
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def convert_file(parser: JapaneseExcelParser, source: Path) -> Path:
    result = parser.parse(str(source))
    output_path = source.with_suffix(".md")
    output_path.write_text(result.text, encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Excel files in the current directory to Markdown.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="File or directory to convert. Default: current directory.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Scan subdirectories too.",
    )
    return parser


def main() -> int:
    _configure_stdout()
    args = build_arg_parser().parse_args()
    base_path = Path(args.target).expanduser().resolve()

    try:
        targets = iter_targets(base_path, args.recursive)
    except Exception as exc:
        print(f"[error] {exc}")
        return 1

    if not targets:
        print(f"[info] no supported Excel files found in: {base_path}")
        return 0

    parser = JapaneseExcelParser()
    success = 0
    failed = 0
    print(f"[info] input: {base_path}")

    for index, source in enumerate(targets, start=1):
        try:
            output_path = convert_file(parser, source)
            success += 1
            print(f"[{index}/{len(targets)}] {source.name} -> {output_path.name}")
        except Exception as exc:
            failed += 1
            print(f"[{index}/{len(targets)}] {source.name} FAILED: {exc}")

    print(f"[done] success={success}, failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
