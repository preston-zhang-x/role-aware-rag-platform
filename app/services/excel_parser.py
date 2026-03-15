"""
日本式 Excel 仕様書の専門パーサー。
三大戦略で「方眼紙Excel」を LLM が理解しやすい Markdown に変換する：
1. 全局上下文注入 (Context Injection)     → Sheet名を # 見出しに
2. 結合セル解構と広播 (Merged Cells)       → None空洞を消滅
3. 混合レイアウト启发式扫描 (Heuristic)   → KV / Table を自動判別
"""

from dataclasses import dataclass, field
from pathlib import Path
import re

import openpyxl
from openpyxl.cell.cell import Cell, MergedCell
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.services.base_parser import BaseParser, ParseError
from app.services.parse_result import (
    BlockKind,
    ChunkMeta,
    ContentType,
    MarkdownEscaper,
    ParseResult,
    ParsedBlock,
    ParserWarning,
)

CellLike = Cell | MergedCell


@dataclass
class StructureHints:
    known_ids: set[str] = field(default_factory=set)


@dataclass
class SemanticRow:
    row_idx: int
    effective_row: list[str]
    semantic_row: list[str]


class JapaneseExcelParser(BaseParser):
    """
    日本式 Excel 仕様書に特化したパーサー。
    """

    MAX_HEADING_LENGTH = 48
    ID_HEADER_HINTS = ("ID", "番号", "NO", "NO.", "KEY", "CODE", "コード")
    ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}(?:-[A-Z0-9]+)+\b")
    RECORD_HEADING_PATTERN = re.compile(
        r"^(?P<record_id>[A-Z][A-Z0-9]{1,9}(?:-[A-Z0-9]+)+)"
        r"(?:\s+(?P<title>.+))?$"
    )

    def __init__(self, density_threshold: float = 0.5):
        self.density_threshold = density_threshold

    def can_handle(self, file_path: str) -> bool:
        suffix = Path(file_path).suffix.lower()
        return suffix in {".xlsx", ".xlsm"}

    def parse(self, file_path: str) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"ファイルが見つかりません: {file_path}", file_path)

        all_chunks: list[ChunkMeta] = []
        all_warnings: list[str] = []
        all_blocks: list[ParsedBlock] = []
        markdown_sections: list[str] = []

        try:
            wb_cached = openpyxl.load_workbook(file_path, data_only=True)
            wb_formula = openpyxl.load_workbook(file_path, data_only=False)
        except Exception as e:
            raise ParseError(f"Excelファイルの読み込みに失敗: {e}", file_path)

        structure_hints = self._build_structure_hints(wb_cached)

        try:
            for sheet_name in wb_cached.sheetnames:
                ws_cached = wb_cached[sheet_name]
                ws_formula = wb_formula[sheet_name]

                if ws_cached.sheet_state != "visible":
                    all_warnings.append(
                        f"{ParserWarning.HIDDEN_SHEET_SKIPPED.value}: {sheet_name}"
                    )
                    continue

                markdown_sections.append(f"# {sheet_name}")

                grid, broadcast_cells = self._build_grid_with_merged_cells(
                    ws_cached, ws_formula, all_warnings
                )
                if not grid:
                    markdown_sections.append("_(空のシート)_")
                    continue

                section_md, section_chunks, legacy_blocks = self._heuristic_scan(
                    grid,
                    file_path,
                    sheet_name,
                    broadcast_cells,
                    structure_hints,
                )
                if section_md:
                    markdown_sections.append(section_md)
                all_chunks.extend(section_chunks)

                special_blocks = self._build_semantic_blocks(
                    grid,
                    file_path,
                    sheet_name,
                    broadcast_cells,
                    structure_hints,
                )

                all_blocks.extend(special_blocks or legacy_blocks)

                shapes_md = self._extract_shapes_and_comments(ws_cached)
                if shapes_md:
                    markdown_sections.append(shapes_md)
                    shape_block = self._build_block(
                        shapes_md,
                        ChunkMeta(
                            source_file=file_path,
                            content_type=ContentType.SHAPE,
                            sheet_name=sheet_name,
                            block_kind=BlockKind.SHEET_SUMMARY,
                        ),
                    )
                    if shape_block:
                        all_blocks.append(shape_block)
        finally:
            wb_cached.close()
            wb_formula.close()

        return ParseResult(
            text="\n\n".join(
                section.strip() for section in markdown_sections if section.strip()
            )
            + "\n",
            chunks=all_chunks,
            warnings=all_warnings,
            blocks=all_blocks,
        )

    def _build_grid_with_merged_cells(
        self,
        ws_cached: Worksheet,
        ws_formula: Worksheet,
        warnings: list[str],
    ) -> tuple[list[list[str]], set[tuple[int, int]]]:
        if ws_cached.max_row is None or ws_cached.max_column is None:
            return [], set()

        max_row = ws_cached.max_row
        max_col = ws_cached.max_column
        broadcast_cells: set[tuple[int, int]] = set()
        grid: list[list[str]] = [["" for _ in range(max_col)] for _ in range(max_row)]

        for row_idx in range(1, max_row + 1):
            for col_idx in range(1, max_col + 1):
                value = self._read_cell_value(
                    ws_cached.cell(row=row_idx, column=col_idx),
                    ws_formula.cell(row=row_idx, column=col_idx),
                    warnings,
                )
                grid[row_idx - 1][col_idx - 1] = value

        for merged_range in ws_cached.merged_cells.ranges:
            top_left_value = grid[merged_range.min_row - 1][merged_range.min_col - 1]
            for row_idx in range(merged_range.min_row, merged_range.max_row + 1):
                for col_idx in range(merged_range.min_col, merged_range.max_col + 1):
                    grid[row_idx - 1][col_idx - 1] = top_left_value
                    if (
                        row_idx != merged_range.min_row
                        or col_idx != merged_range.min_col
                    ):
                        broadcast_cells.add((row_idx - 1, col_idx - 1))

            warnings.append(
                f"{ParserWarning.MERGED_CELL_BROADCAST.value}: {merged_range}"
            )
        return grid, broadcast_cells

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
        broadcast_cells: set[tuple[int, int]],
        structure_hints: StructureHints,
    ) -> tuple[str, list[ChunkMeta], list[ParsedBlock]]:
        markdown_parts: list[str] = []
        chunks: list[ChunkMeta] = []
        blocks: list[ParsedBlock] = []

        rows = self._semantic_rows(grid, broadcast_cells)
        if not rows:
            return "", [], []

        effective_cols = self._calc_effective_cols(grid)
        table_buffer: list[list[str]] = []
        table_start_row = 0
        last_text_block: str | None = None
        previous_kv_keys: set[str] = set()

        def flush_table(end_row: int) -> None:
            nonlocal table_buffer
            if not table_buffer:
                return
            md, chunk, block = self._flush_table(
                table_buffer,
                table_start_row,
                end_row,
                file_path,
                sheet_name,
                effective_cols,
                structure_hints,
            )
            if md:
                markdown_parts.append(md)
                chunks.append(chunk)
            if block:
                blocks.append(block)
            table_buffer = []

        for row in rows:
            effective_row = row.effective_row
            semantic_row = row.semantic_row

            if not semantic_row:
                flush_table(row.row_idx - 1)
                previous_kv_keys = set()
                continue

            if len(semantic_row) == 1:
                flush_table(row.row_idx - 1)
                text = MarkdownEscaper.escape_cell(semantic_row[0])
                if self._should_skip_text_block(
                    text, last_text_block, previous_kv_keys
                ):
                    previous_kv_keys = set()
                    continue

                rendered = self._render_text_block(text)
                if not rendered:
                    previous_kv_keys = set()
                    continue

                markdown_parts.append(rendered)
                chunk = ChunkMeta(
                    source_file=file_path,
                    content_type=ContentType.TEXT,
                    sheet_name=sheet_name,
                    cell_range=f"row {row.row_idx + 1}",
                    is_broadcast_fill=sum(cell != "" for cell in effective_row) > 1,
                    block_kind=BlockKind.SHEET_SUMMARY,
                    related_ids=self._scan_related_ids(
                        rendered,
                        structure_hints,
                    ),
                )
                chunks.append(chunk)
                block = self._build_block(rendered, chunk)
                if block:
                    blocks.append(block)
                last_text_block = text
                previous_kv_keys = set()
                continue

            non_empty = sum(1 for cell in effective_row if cell != "")
            row_span = self._calc_row_span(effective_row)
            density = non_empty / row_span if row_span else 0

            if self._looks_like_kv_row(effective_row, semantic_row, density):
                flush_table(row.row_idx - 1)
                kv_md, kv_keys = self._render_kv_row(semantic_row)
                if kv_md:
                    markdown_parts.append(kv_md)
                    chunk = ChunkMeta(
                        source_file=file_path,
                        content_type=ContentType.KEY_VALUE,
                        sheet_name=sheet_name,
                        cell_range=f"row {row.row_idx + 1}",
                        block_kind=BlockKind.LEGACY_KV,
                        related_ids=self._scan_related_ids(
                            kv_md,
                            structure_hints,
                        ),
                    )
                    chunks.append(chunk)
                    block = self._build_block(kv_md, chunk)
                    if block:
                        blocks.append(block)
                    previous_kv_keys = kv_keys
                    last_text_block = None
            else:
                if not table_buffer:
                    table_start_row = row.row_idx
                table_buffer.append(effective_row)
                last_text_block = None
                previous_kv_keys = set()

        flush_table(len(grid) - 1)
        return "\n\n".join(markdown_parts), chunks, blocks

    def _build_structure_hints(self, workbook) -> StructureHints:
        hints = StructureHints()
        for ws in workbook.worksheets:
            if ws.sheet_state != "visible":
                continue
            for row in ws.iter_rows():
                for cell in row:
                    if not isinstance(cell.value, str):
                        continue
                    value = cell.value.strip()
                    if self.ID_PATTERN.fullmatch(value):
                        hints.known_ids.add(value)
        return hints

    def _build_semantic_blocks(
        self,
        grid: list[list[str]],
        file_path: str,
        sheet_name: str,
        broadcast_cells: set[tuple[int, int]],
        structure_hints: StructureHints,
    ) -> list[ParsedBlock]:
        rows = self._semantic_rows(grid, broadcast_cells)
        if not rows:
            return []

        record_blocks = self._build_record_blocks(
            rows,
            file_path,
            sheet_name,
            grid,
            structure_hints,
        )
        if record_blocks:
            return record_blocks

        return self._build_id_list_blocks(
            rows,
            file_path,
            sheet_name,
            structure_hints,
        )

    def _build_record_blocks(
        self,
        rows: list[SemanticRow],
        file_path: str,
        sheet_name: str,
        grid: list[list[str]],
        structure_hints: StructureHints,
    ) -> list[ParsedBlock]:
        headings = self._record_heading_positions(rows, structure_hints)
        if not headings:
            return []

        blocks: list[ParsedBlock] = []
        for position_index, (heading_pos, (record_id, title)) in enumerate(headings):
            next_pos = (
                headings[position_index + 1][0]
                if position_index + 1 < len(headings)
                else len(rows)
            )
            record_rows = rows[heading_pos:next_pos]
            summary_rows: list[SemanticRow] = []
            record_blocks: list[ParsedBlock] = []

            index = 1
            while index < len(record_rows):
                row = record_rows[index]
                id_table = self._collect_id_table(
                    record_rows,
                    index,
                    structure_hints,
                    min_data_rows=1,
                )
                if id_table is not None:
                    _, child_header, child_rows, next_index = id_table
                    for child_row in child_rows:
                        child_block = self._build_child_record_block(
                            file_path=file_path,
                            sheet_name=sheet_name,
                            parent_record_id=record_id,
                            headers=child_header.semantic_row,
                            row=child_row,
                            structure_hints=structure_hints,
                        )
                        if child_block:
                            record_blocks.append(child_block)
                    index = next_index
                    continue

                if self._is_section_anchor(record_rows, index, structure_hints):
                    section_row = record_rows[index]
                    next_index = index + 1
                    while next_index < len(record_rows):
                        if self._is_section_anchor(
                            record_rows,
                            next_index,
                            structure_hints,
                        ):
                            break
                        if self._collect_id_table(
                            record_rows,
                            next_index,
                            structure_hints,
                            min_data_rows=1,
                        ):
                            break
                        next_index += 1

                    section_text = self._render_record_section_text(
                        record_id=record_id,
                        section_name=section_row.semantic_row[0].strip(),
                        rows=record_rows[index + 1 : next_index],
                    )
                    if section_text:
                        section_end_row = (
                            record_rows[next_index - 1].row_idx
                            if next_index - 1 > index
                            else section_row.row_idx
                        )
                        meta = ChunkMeta(
                            source_file=file_path,
                            content_type=ContentType.KEY_VALUE,
                            sheet_name=sheet_name,
                            cell_range=self._span_cell_range(
                                section_row.row_idx,
                                section_end_row,
                                self._calc_effective_cols(grid),
                            ),
                            block_kind=BlockKind.RECORD_SECTION,
                            record_id=record_id,
                            record_type=self._record_type(record_id),
                            section_name=section_row.semantic_row[0].strip(),
                            related_ids=self._scan_related_ids(
                                section_text,
                                structure_hints,
                                exclude={record_id},
                            ),
                        )
                        block = self._build_block(section_text, meta)
                        if block:
                            record_blocks.append(block)
                    index = next_index
                    continue

                summary_rows.append(row)
                index += 1

            summary_lines = [f"## {record_id}" + (f" {title}" if title else "")]
            summary_lines.extend(self._render_summary_rows(summary_rows))
            summary_text = "\n".join(summary_lines)
            summary_meta = ChunkMeta(
                source_file=file_path,
                content_type=ContentType.KEY_VALUE,
                sheet_name=sheet_name,
                cell_range=self._span_cell_range(
                    record_rows[0].row_idx,
                    summary_rows[-1].row_idx if summary_rows else record_rows[0].row_idx,
                    self._calc_effective_cols(grid),
                ),
                block_kind=BlockKind.RECORD_SUMMARY,
                record_id=record_id,
                record_type=self._record_type(record_id),
                related_ids=self._scan_related_ids(
                    summary_text,
                    structure_hints,
                    exclude={record_id},
                ),
            )
            summary_block = self._build_block(summary_text, summary_meta)
            if summary_block:
                blocks.append(summary_block)
            blocks.extend(record_blocks)

        return self._dedupe_blocks(blocks)

    def _build_id_list_blocks(
        self,
        rows: list[SemanticRow],
        file_path: str,
        sheet_name: str,
        structure_hints: StructureHints,
    ) -> list[ParsedBlock]:
        blocks: list[ParsedBlock] = []
        summary_added = False
        index = 0
        while index < len(rows):
            id_table = self._collect_id_table(
                rows,
                index,
                structure_hints,
                min_data_rows=2,
            )
            if id_table is None:
                index += 1
                continue

            header_index, header_row, data_rows, next_index = id_table
            if not summary_added:
                summary_block = self._build_sheet_summary_block(
                    file_path=file_path,
                    sheet_name=sheet_name,
                    header_row=header_row,
                    intro_rows=rows[:header_index],
                    structure_hints=structure_hints,
                )
                if summary_block:
                    blocks.append(summary_block)
                summary_added = True

            headers = header_row.semantic_row
            for row in data_rows:
                record_id = row.semantic_row[0]
                title = self._choose_record_title(headers, row.semantic_row, record_id)
                lines = [f"## {record_id}" + (f" {title}" if title else "")]
                for header, value in zip(headers, row.semantic_row):
                    if not header or not value or self._is_placeholder_value(value):
                        continue
                    lines.append(f"- {header}: {value}")
                block_text = "\n".join(lines)
                meta = ChunkMeta(
                    source_file=file_path,
                    content_type=ContentType.KEY_VALUE,
                    sheet_name=sheet_name,
                    cell_range=self._row_cell_range(row.row_idx, row.effective_row),
                    block_kind=BlockKind.RECORD_SUMMARY,
                    record_id=record_id,
                    record_type=self._record_type(record_id),
                    related_ids=self._scan_related_ids(
                        block_text,
                        structure_hints,
                        exclude={record_id},
                    ),
                )
                block = self._build_block(block_text, meta)
                if block:
                    blocks.append(block)
            index = next_index

        return self._dedupe_blocks(blocks)

    def _build_sheet_summary_block(
        self,
        file_path: str,
        sheet_name: str,
        header_row: SemanticRow,
        intro_rows: list[SemanticRow],
        structure_hints: StructureHints,
    ) -> ParsedBlock | None:
        summary_lines = [f"## {sheet_name}"]
        summary_lines.extend(self._collect_intro_lines(intro_rows, sheet_name))
        if header_row.semantic_row:
            summary_lines.append(f"- columns: {', '.join(header_row.semantic_row)}")
        summary_text = "\n".join(summary_lines)
        summary_meta = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.TEXT,
            sheet_name=sheet_name,
            cell_range=self._span_cell_range(
                0,
                header_row.row_idx,
                len(header_row.semantic_row) or len(header_row.effective_row),
            ),
            block_kind=BlockKind.SHEET_SUMMARY,
            related_ids=self._scan_related_ids(summary_text, structure_hints),
        )
        return self._build_block(summary_text, summary_meta)

    def _build_child_record_block(
        self,
        *,
        file_path: str,
        sheet_name: str,
        parent_record_id: str,
        headers: list[str],
        row: SemanticRow,
        structure_hints: StructureHints,
    ) -> ParsedBlock | None:
        child_id = row.semantic_row[0]
        lines = [f"## {child_id}", f"- parent_record_id: {parent_record_id}"]
        for header, value in zip(headers, row.semantic_row):
            if not header or not value or self._is_placeholder_value(value):
                continue
            lines.append(f"- {header}: {value}")
        block_text = "\n".join(lines)
        meta = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.KEY_VALUE,
            sheet_name=sheet_name,
            cell_range=self._row_cell_range(row.row_idx, row.effective_row),
            block_kind=BlockKind.RECORD_ROW,
            record_id=child_id,
            parent_record_id=parent_record_id,
            record_type=self._record_type(child_id),
            related_ids=self._scan_related_ids(
                block_text,
                structure_hints,
                exclude={child_id},
            ),
        )
        return self._build_block(block_text, meta)

    def _collect_id_table(
        self,
        rows: list[SemanticRow],
        start_index: int,
        structure_hints: StructureHints,
        min_data_rows: int,
    ) -> tuple[int, SemanticRow, list[SemanticRow], int] | None:
        if start_index >= len(rows):
            return None
        header_row = rows[start_index]
        if not header_row.semantic_row:
            return None
        if not self._looks_like_id_header(header_row.semantic_row[0]):
            return None

        data_rows: list[SemanticRow] = []
        index = start_index + 1
        while index < len(rows):
            row = rows[index]
            if not row.semantic_row:
                if data_rows:
                    break
                index += 1
                continue
            if not self._is_id_value(row.semantic_row[0], structure_hints):
                break
            data_rows.append(row)
            index += 1

        if len(data_rows) < min_data_rows:
            return None
        return start_index, header_row, data_rows, index

    def _is_section_anchor(
        self,
        rows: list[SemanticRow],
        index: int,
        structure_hints: StructureHints,
    ) -> bool:
        if index >= len(rows):
            return False
        row = rows[index]
        if len(row.semantic_row) != 1:
            return False
        text = row.semantic_row[0].strip()
        if not text or self._is_placeholder_value(text):
            return False
        if self._extract_record_heading(text, structure_hints) is not None:
            return False
        if not self._looks_like_heading(text):
            return False

        for candidate in rows[index + 1 :]:
            if not candidate.semantic_row:
                continue
            if len(candidate.semantic_row) == 1:
                candidate_text = candidate.semantic_row[0].strip()
                if self._extract_record_heading(candidate_text, structure_hints):
                    return False
                return not self._looks_like_heading(candidate_text)
            return True
        return False

    def _render_record_section_text(
        self,
        record_id: str,
        section_name: str,
        rows: list[SemanticRow],
    ) -> str:
        table_text = self._render_tabular_section_text(record_id, section_name, rows)
        if table_text:
            return table_text

        lines = [f"## {record_id} / {section_name}"]
        lines.extend(self._render_summary_rows(rows))
        return "\n".join(lines) if len(lines) > 1 else ""

    def _render_tabular_section_text(
        self,
        record_id: str,
        section_name: str,
        rows: list[SemanticRow],
    ) -> str:
        table_rows = [row.semantic_row for row in rows if row.semantic_row]
        if len(table_rows) < 2:
            return ""
        headers = table_rows[0]
        data_rows = [
            row for row in table_rows[1:] if self._row_has_meaningful_values(row)
        ]
        if not data_rows:
            return ""

        lines = [f"## {record_id} / {section_name}"]
        if len(data_rows) == 1:
            for header, value in zip(headers, data_rows[0]):
                if not header or not value or self._is_placeholder_value(value):
                    continue
                lines.append(f"- {header}: {value}")
        else:
            primary_index = self._primary_column_index(headers)
            for row in data_rows:
                primary = self._primary_value(row, primary_index)
                fields: list[str] = []
                for header, value in zip(headers, row):
                    if not header or not value or self._is_placeholder_value(value):
                        continue
                    if (
                        primary_index is not None
                        and header == headers[primary_index]
                        and value == primary
                    ):
                        continue
                    fields.append(f"{header}={value}")
                if primary and fields:
                    lines.append(f"- {primary} | " + " | ".join(fields))
                elif primary:
                    lines.append(f"- {primary}")
                elif fields:
                    lines.append("- " + " | ".join(fields))
        return "\n".join(lines) if len(lines) > 1 else ""

    def _dedupe_blocks(self, blocks: list[ParsedBlock]) -> list[ParsedBlock]:
        deduped: list[ParsedBlock] = []
        seen: set[tuple[str, str | None, str | None, str | None, str]] = set()
        for block in blocks:
            key = (
                block.meta.block_kind.value if block.meta.block_kind else "",
                block.meta.record_id,
                block.meta.parent_record_id,
                block.meta.section_name,
                block.text,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(block)
        return deduped

    def _collapse_duplicate_runs(
        self,
        row: list[str],
        row_idx: int,
        broadcast_cells: set[tuple[int, int]],
    ) -> list[str]:
        collapsed: list[str] = []
        previous_value: str | None = None
        previous_was_broadcast = False

        for col_idx, cell in enumerate(row):
            is_broadcast = (row_idx, col_idx) in broadcast_cells
            if cell == "":
                previous_value = None
                previous_was_broadcast = False
                continue
            if cell != previous_value or not (is_broadcast or previous_was_broadcast):
                collapsed.append(cell)
            previous_was_broadcast = is_broadcast
            previous_value = cell

        return collapsed

    def _has_internal_blank_gap(self, row: list[str]) -> bool:
        try:
            first = next(index for index, cell in enumerate(row) if cell != "")
            last = max(index for index, cell in enumerate(row) if cell != "")
        except (StopIteration, ValueError):
            return False

        return any(cell == "" for cell in row[first : last + 1])

    def _calc_row_span(self, row: list[str]) -> int:
        try:
            first = next(index for index, cell in enumerate(row) if cell != "")
            last = max(index for index, cell in enumerate(row) if cell != "")
        except (StopIteration, ValueError):
            return 0

        return last - first + 1

    def _looks_like_heading(self, text: str) -> bool:
        normalized = text.strip()
        if not normalized or self._is_placeholder_value(normalized):
            return False
        if len(normalized) > self.MAX_HEADING_LENGTH:
            return False
        if any(token in normalized for token in ("。", "<br>", r"\|", ":", "：")):
            return False
        return True

    def _render_text_block(self, text: str) -> str:
        if self._is_placeholder_value(text):
            return ""
        if self._looks_like_heading(text):
            return f"## {text}"
        return text

    def _should_skip_text_block(
        self,
        text: str,
        last_text_block: str | None,
        previous_kv_keys: set[str],
    ) -> bool:
        if self._is_placeholder_value(text):
            return True
        if text == last_text_block:
            return True
        if text in previous_kv_keys and len(text) <= 24:
            return True
        return False

    def _looks_like_kv_row(
        self,
        original_row: list[str],
        semantic_row: list[str],
        density: float,
    ) -> bool:
        if len(semantic_row) <= 1:
            return False

        if density < self.density_threshold:
            return True

        non_empty_original = sum(1 for cell in original_row if cell != "")
        was_compacted = len(semantic_row) < non_empty_original
        has_internal_blank_gap = self._has_internal_blank_gap(original_row)
        try:
            first_non_empty = next(
                index for index, cell in enumerate(original_row) if cell != ""
            )
        except (StopIteration, ValueError):
            first_non_empty = -1

        if len(semantic_row) == 2 and first_non_empty > 0:
            return True

        if len(semantic_row) <= 6 and (was_compacted or has_internal_blank_gap):
            return True

        return False

    def _calc_effective_cols(self, grid: list[list[str]]) -> int:
        if not grid:
            return 0
        max_col = len(grid[0])
        for col_idx in range(max_col - 1, -1, -1):
            if any(grid[row_idx][col_idx] != "" for row_idx in range(len(grid))):
                return col_idx + 1
        return 0

    def _flush_table(
        self,
        buffer: list[list[str]],
        start_row: int,
        end_row: int,
        file_path: str,
        sheet_name: str,
        effective_cols: int,
        structure_hints: StructureHints,
    ) -> tuple[str, ChunkMeta, ParsedBlock | None]:
        empty_meta = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.TABLE,
            sheet_name=sheet_name,
        )
        if not buffer:
            return "", empty_meta, None

        table_cols = self._calc_effective_cols(buffer)
        if table_cols == 0:
            return "", empty_meta, None

        trimmed_buffer = [row[:table_cols] for row in buffer]
        headers = trimmed_buffer[0]
        data_rows = trimmed_buffer[1:] if len(trimmed_buffer) > 1 else []
        meaningful_rows = [
            row for row in data_rows if self._row_has_meaningful_values(row)
        ]
        if not meaningful_rows:
            return "", empty_meta, None

        md = MarkdownEscaper.make_table(headers, meaningful_rows)
        cell_range = (
            f"{get_column_letter(1)}{start_row + 1}:"
            f"{get_column_letter(table_cols)}{end_row + 1}"
        )
        chunk = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.TABLE,
            sheet_name=sheet_name,
            cell_range=cell_range,
            block_kind=BlockKind.LEGACY_TABLE,
            related_ids=self._scan_related_ids(md, structure_hints),
        )
        block = self._build_block(md, chunk)
        return md, chunk, block

    def _render_kv_row(self, row: list[str]) -> tuple[str, set[str]]:
        if not row or not self._row_has_meaningful_values(row):
            return "", set()
        parts: list[str] = []
        keys: set[str] = set()
        index = 0
        while index < len(row):
            key = row[index]
            value = row[index + 1] if index + 1 < len(row) else ""
            if self._is_placeholder_value(key) and self._is_placeholder_value(value):
                index += 2
                continue
            escaped_key = MarkdownEscaper.escape_cell(key)
            escaped_value = MarkdownEscaper.escape_cell(value)
            if escaped_key and not self._is_placeholder_value(escaped_key):
                keys.add(escaped_key)
            if escaped_key and escaped_value and not self._is_placeholder_value(
                escaped_value
            ):
                parts.append(f"- **{escaped_key}:** {escaped_value}")
            elif escaped_key and not self._is_placeholder_value(escaped_key):
                parts.append(f"- {escaped_key}")
            index += 2
        return "\n".join(parts), keys

    def _extract_shapes_and_comments(self, ws: Worksheet) -> str:
        comments_md: list[str] = []
        for row in ws.iter_rows():
            for cell in row:
                if cell.comment:
                    column_index = cell.column
                    if column_index is None:
                        continue
                    coord = f"{get_column_letter(column_index)}{cell.row}"
                    comment_text = MarkdownEscaper.escape_cell(cell.comment.text)
                    comments_md.append(f"- **[{coord}]** {comment_text}")
        if not comments_md:
            return ""
        return "### コメント・注記\n\n" + "\n".join(comments_md)

    def _semantic_rows(
        self,
        grid: list[list[str]],
        broadcast_cells: set[tuple[int, int]],
    ) -> list[SemanticRow]:
        effective_cols = self._calc_effective_cols(grid)
        rows: list[SemanticRow] = []
        for row_idx, row in enumerate(grid):
            effective_row = row[:effective_cols]
            semantic_row = self._collapse_duplicate_runs(
                effective_row,
                row_idx,
                broadcast_cells,
            )
            if semantic_row and len(set(semantic_row)) == 1:
                semantic_row = [semantic_row[0]]
            rows.append(
                SemanticRow(
                    row_idx=row_idx,
                    effective_row=effective_row,
                    semantic_row=semantic_row,
                )
            )
        return rows

    def _record_heading_positions(
        self,
        rows: list[SemanticRow],
        structure_hints: StructureHints,
    ) -> list[tuple[int, tuple[str, str]]]:
        positions: list[tuple[int, tuple[str, str]]] = []
        for index, row in enumerate(rows):
            if len(row.semantic_row) != 1:
                continue
            heading = self._extract_record_heading(row.semantic_row[0], structure_hints)
            if heading is not None:
                positions.append((index, heading))
        return positions

    def _extract_record_heading(
        self,
        text: str,
        structure_hints: StructureHints,
    ) -> tuple[str, str] | None:
        normalized = text.strip()
        match = self.RECORD_HEADING_PATTERN.match(normalized)
        if not match:
            return None
        record_id = match.group("record_id")
        if not self._is_id_value(record_id, structure_hints):
            return None
        title = (match.group("title") or "").strip()
        return record_id, title

    def _is_id_value(self, text: str, structure_hints: StructureHints) -> bool:
        normalized = text.strip()
        if not normalized:
            return False
        if normalized in structure_hints.known_ids:
            return True
        return self.ID_PATTERN.fullmatch(normalized) is not None

    def _record_type(self, record_id: str) -> str:
        return record_id.split("-", 1)[0]

    def _looks_like_id_header(self, text: str) -> bool:
        normalized = text.strip().upper()
        if not normalized:
            return False
        if any(hint in normalized for hint in self.ID_HEADER_HINTS):
            return True
        if self.ID_PATTERN.fullmatch(normalized):
            return False
        return False

    def _collect_intro_lines(
        self,
        rows: list[SemanticRow],
        sheet_name: str,
    ) -> list[str]:
        lines: list[str] = []
        for row in rows:
            if len(row.semantic_row) != 1:
                continue
            text = MarkdownEscaper.escape_cell(row.semantic_row[0])
            if not text or text == sheet_name or self._is_placeholder_value(text):
                continue
            lines.append(text)
        return lines

    def _choose_record_title(
        self,
        headers: list[str],
        row: list[str],
        record_id: str,
    ) -> str | None:
        title_candidates = {
            "名称",
            "名前",
            "NAME",
            "TITLE",
            "機能名",
            "画面名",
            "項目名",
            "テーブル名",
            "カラム名",
            "項目",
        }
        for header, value in zip(headers, row):
            if value == record_id or self._is_placeholder_value(value):
                continue
            if header in title_candidates:
                return value
        for value in row[1:]:
            if value and not self._is_placeholder_value(value):
                return value
        return None

    def _render_summary_rows(self, rows: list[SemanticRow]) -> list[str]:
        lines: list[str] = []
        for row in rows:
            if not row.semantic_row or self._row_is_placeholder(row.semantic_row):
                continue
            if len(row.semantic_row) == 1:
                text = MarkdownEscaper.escape_cell(row.semantic_row[0])
                if text and not self._is_placeholder_value(text):
                    lines.append(text)
                continue
            for key, value in self._pairwise(row.semantic_row):
                if not key or self._is_placeholder_value(key):
                    continue
                if value and not self._is_placeholder_value(value):
                    lines.append(f"- {key}: {value}")
                else:
                    lines.append(f"- {key}")
        return lines

    def _primary_column_index(self, headers: list[str]) -> int | None:
        if "項目名" in headers:
            return headers.index("項目名")
        for index, header in enumerate(headers):
            if header and not self._is_placeholder_value(header):
                return index
        return None

    def _primary_value(self, row: list[str], primary_index: int | None) -> str:
        if primary_index is not None and primary_index < len(row):
            value = row[primary_index]
            if value and not self._is_placeholder_value(value):
                return value
        for value in row:
            if value and not self._is_placeholder_value(value):
                return value
        return ""

    def _pairwise(self, row: list[str]) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        index = 0
        while index < len(row):
            key = MarkdownEscaper.escape_cell(row[index])
            value = (
                MarkdownEscaper.escape_cell(row[index + 1])
                if index + 1 < len(row)
                else ""
            )
            pairs.append((key, value))
            index += 2
        return pairs

    def _row_has_meaningful_values(self, row: list[str]) -> bool:
        return any(value and not self._is_placeholder_value(value) for value in row)

    def _row_is_placeholder(self, row: list[str]) -> bool:
        values = [value for value in row if value != ""]
        return bool(values) and all(self._is_placeholder_value(value) for value in values)

    def _is_placeholder_value(self, value: str | None) -> bool:
        if value is None:
            return True
        normalized = MarkdownEscaper.escape_cell(value).replace("<br>", "").strip()
        return normalized == "-"

    def _build_block(
        self,
        text: str,
        meta: ChunkMeta,
    ) -> ParsedBlock | None:
        normalized = text.strip()
        if not normalized:
            return None
        return ParsedBlock(text=normalized, meta=meta)

    def _scan_related_ids(
        self,
        text: str,
        structure_hints: StructureHints,
        exclude: set[str] | None = None,
    ) -> list[str]:
        exclude = exclude or set()
        matches = self.ID_PATTERN.findall(text)
        ordered = [match for match in matches if match in structure_hints.known_ids]
        ordered.extend(match for match in matches if match not in structure_hints.known_ids)
        related_ids: list[str] = []
        seen: set[str] = set()
        for match in ordered:
            if match in exclude or match in seen:
                continue
            seen.add(match)
            related_ids.append(match)
        return related_ids

    def _span_cell_range(self, start_row: int, end_row: int, width: int) -> str | None:
        if width <= 0:
            return None
        return f"A{start_row + 1}:{get_column_letter(width)}{end_row + 1}"

    def _row_cell_range(self, row_idx: int, row: list[str]) -> str | None:
        non_empty = [index for index, value in enumerate(row) if value != ""]
        if not non_empty:
            return None
        start = get_column_letter(non_empty[0] + 1)
        end = get_column_letter(non_empty[-1] + 1)
        return f"{start}{row_idx + 1}:{end}{row_idx + 1}"
