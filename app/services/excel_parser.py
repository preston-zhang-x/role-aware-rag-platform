"""
日本式 Excel 仕様書の専門パーサー。
三大戦略で「方眼紙Excel」を LLM が理解しやすい Markdown に変換する：
1. 全局上下文注入 (Context Injection)     → Sheet名を # 見出しに
2. 結合セル解構と広播 (Merged Cells)       → None空洞を消滅
3. 混合レイアウト启发式扫描 (Heuristic)   → KV / Table を自動判別
"""

from pathlib import Path

import openpyxl
from openpyxl.cell.cell import Cell, MergedCell
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.services.base_parser import BaseParser, ParseError
from app.services.parse_result import (
    ChunkMeta,
    ContentType,
    MarkdownEscaper,
    ParseResult,
    ParserWarning,
)

CellLike = Cell | MergedCell


class JapaneseExcelParser(BaseParser):
    """
    日本式 Excel 仕様書に特化したパーサー。
    """

    MAX_HEADING_LENGTH = 48

    # ─── コンストラクタ ───
    def __init__(self, density_threshold: float = 0.5):
        """
        density_threshold: 行密度の閾値。
        これを超えるとテーブル行、下回るとKV行と判定。
        デフォルト 0.5 = 50%以上の列にデータがあればテーブル。
        """
        self.density_threshold = density_threshold

    # ─── BaseParser インターフェース実装 ───
    def can_handle(self, file_path: str) -> bool:
        """拡張子で判定: .xlsx, .xlsm"""
        suffix = Path(file_path).suffix.lower()
        return suffix in {".xlsx", ".xlsm"}

    def parse(self, file_path: str) -> ParseResult:
        """
        メインエントリーポイント。
        ファイル全体を Markdown に変換して ParseResult を返す。
        """
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"ファイルが見つかりません: {file_path}", file_path)

        all_chunks: list[ChunkMeta] = []
        all_warnings: list[str] = []
        markdown_sections: list[str] = []

        # ── 公式の二重読み取り ──
        # data_only=True:  キャッシュされた計算結果を読む
        # data_only=False: 数式そのものを読む
        try:
            wb_cached = openpyxl.load_workbook(file_path, data_only=True)
            wb_formula = openpyxl.load_workbook(file_path, data_only=False)
        except Exception as e:
            raise ParseError(f"Excelファイルの読み込みに失敗: {e}", file_path)

        try:
            for sheet_name in wb_cached.sheetnames:
                ws_cached = wb_cached[sheet_name]
                ws_formula = wb_formula[sheet_name]

                # ── 戦略1: 非表示シートをスキップ ──
                if ws_cached.sheet_state != "visible":
                    all_warnings.append(
                        f"{ParserWarning.HIDDEN_SHEET_SKIPPED.value}: {sheet_name}"
                    )
                    continue

                # ── 戦略1: Sheet名を Markdown 一級見出しとして注入 ──
                markdown_sections.append(f"# {sheet_name}")

                # ── 戦略2: 結合セルの解構と広播 ──
                grid, broadcast_cells = self._build_grid_with_merged_cells(
                    ws_cached, ws_formula, all_warnings
                )
                if not grid:
                    markdown_sections.append("_(空のシート)_")
                    continue

                # ── 戦略3: 启发式扫描でKV/テーブルを判別 ──
                section_md, section_chunks = self._heuristic_scan(
                    grid, file_path, sheet_name, broadcast_cells
                )
                markdown_sections.append(section_md)
                all_chunks.extend(section_chunks)

                # ── TextBox / コメントの抽出 ──
                shapes_md = self._extract_shapes_and_comments(ws_cached)
                if shapes_md:
                    markdown_sections.append(shapes_md)

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
        )

    # ═══════════════════════════════════════════════
    # 戦略2: 結合セル解構と広播
    # ═══════════════════════════════════════════════
    def _build_grid_with_merged_cells(
        self,
        ws_cached: Worksheet,
        ws_formula: Worksheet,
        warnings: list[str],
    ) -> tuple[list[list[str]], set[tuple[int, int]]]:
        """
        ワークシートの全セルを2Dリスト(grid)に読み込む。
        結合セルの値を全子セルに広播填充する。
        """
        if ws_cached.max_row is None or ws_cached.max_column is None:
            return [], set()

        max_row = ws_cached.max_row
        max_col = ws_cached.max_column
        broadcast_cells: set[tuple[int, int]] = set()

        # ── Step A: 空の2Dグリッドを初期化 ──
        grid: list[list[str]] = [["" for _ in range(max_col)] for _ in range(max_row)]

        # ── Step B: 通常セルの値を読み込む ──
        for row_idx in range(1, max_row + 1):
            for col_idx in range(1, max_col + 1):
                value = self._read_cell_value(
                    ws_cached.cell(row=row_idx, column=col_idx),
                    ws_formula.cell(row=row_idx, column=col_idx),
                    warnings,
                )
                grid[row_idx - 1][col_idx - 1] = value  # 0-indexed に変換

        # ── Step C: 結合セルの広播填充 ──
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
        """
        セル値の二重読み取り。
        キャッシュ値優先、なければ数式テキストをフォールバック。
        """
        cached_value = cached_cell.value
        formula_value = formula_cell.value

        # ケース1: キャッシュ値がある → そのまま使う
        if cached_value is not None:
            return str(cached_value)

        # ケース2: キャッシュ値がないが数式がある → 数式テキストを保持して警告を出す
        if formula_value is not None and str(formula_value).startswith("="):
            warnings.append(f"{ParserWarning.FORMULA_NO_CACHE.value}: {formula_value}")
            return f"formula: {formula_value}"

        # ケース3: 完全に空
        return ""

    # ═══════════════════════════════════════════════
    # 戦略3: 启发式扫描 — KV vs Table 判定
    # ═══════════════════════════════════════════════
    def _heuristic_scan(
        self,
        grid: list[list[str]],
        file_path: str,
        sheet_name: str,
        broadcast_cells: set[tuple[int, int]],
    ) -> tuple[str, list[ChunkMeta]]:
        """
        行ごとにデータ密度を計算し、KV(疎)/ Table(密)を動的に切り替え。
        """
        markdown_parts: list[str] = []
        chunks: list[ChunkMeta] = []

        # 有効列数を計算（全行が空の末尾列を除外）
        effective_cols = self._calc_effective_cols(grid)
        if effective_cols == 0:
            return "", []

        # テーブル行のバッファ（連続モードで蓄積）
        table_buffer: list[list[str]] = []
        table_start_row: int = 0
        last_text_block: str | None = None
        previous_kv_keys: set[str] = set()

        def flush_table(end_row: int) -> None:
            nonlocal table_buffer
            if not table_buffer:
                return
            md, chunk = self._flush_table(
                table_buffer,
                table_start_row,
                end_row,
                file_path,
                sheet_name,
                effective_cols,
            )
            if md:
                markdown_parts.append(md)
                chunks.append(chunk)
            table_buffer = []

        for row_idx, row in enumerate(grid):
            # 有効列のみ切り出し
            effective_row = row[:effective_cols]
            semantic_row = self._collapse_duplicate_runs(
                effective_row, row_idx, broadcast_cells
            )
            if semantic_row and len(set(semantic_row)) == 1:
                semantic_row = [semantic_row[0]]

            # 空行判定
            if not semantic_row:
                flush_table(row_idx - 1)
                previous_kv_keys = set()
                continue

            if len(semantic_row) == 1:
                flush_table(row_idx - 1)
                text = MarkdownEscaper.escape_cell(semantic_row[0])
                if self._should_skip_text_block(
                    text, last_text_block, previous_kv_keys
                ):
                    previous_kv_keys = set()
                    continue

                markdown_parts.append(self._render_text_block(text))
                chunks.append(
                    ChunkMeta(
                        source_file=file_path,
                        content_type=ContentType.TEXT,
                        sheet_name=sheet_name,
                        cell_range=f"row {row_idx + 1}",
                        is_broadcast_fill=sum(cell != "" for cell in effective_row) > 1,
                    )
                )
                last_text_block = text
                previous_kv_keys = set()
                continue

            # ── 密度計算 ──
            non_empty = sum(1 for cell in effective_row if cell != "")
            row_span = self._calc_row_span(effective_row)
            density = non_empty / row_span if row_span else 0

            if self._looks_like_kv_row(effective_row, semantic_row, density):
                # ── 離散モード → KV ──
                # まずバッファフラッシュ
                flush_table(row_idx - 1)

                kv_md, kv_keys = self._render_kv_row(semantic_row)
                if kv_md:
                    markdown_parts.append(kv_md)
                    chunks.append(
                        ChunkMeta(
                            source_file=file_path,
                            content_type=ContentType.KEY_VALUE,
                            sheet_name=sheet_name,
                            cell_range=f"row {row_idx + 1}",
                        )
                    )
                    previous_kv_keys = kv_keys
                    last_text_block = None
            else:
                # ── 連続モード → テーブルバッファに追加 ──
                if not table_buffer:
                    table_start_row = row_idx
                table_buffer.append(effective_row)
                last_text_block = None
                previous_kv_keys = set()

        # ループ終了後、残りバッファをフラッシュ
        flush_table(len(grid) - 1)

        return "\n\n".join(markdown_parts), chunks

    # ═══════════════════════════════════════════════
    # ヘルパーメソッド群
    # ═══════════════════════════════════════════════

    def _collapse_duplicate_runs(
        self,
        row: list[str],
        row_idx: int,
        broadcast_cells: set[tuple[int, int]],
    ) -> list[str]:
        """
        結合セルのブロードキャストで横方向に重複した値を 1 回に畳み込む。
        空セルは区切りとして扱い、離れた位置の同値は別要素として残す。
        """
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
        """
        非空セルの途中に空白ギャップがある行を検出する。
        KV レイアウトや結合セルペアの手掛かりに使う。
        """
        try:
            first = next(index for index, cell in enumerate(row) if cell != "")
            last = max(index for index, cell in enumerate(row) if cell != "")
        except (StopIteration, ValueError):
            return False

        return any(cell == "" for cell in row[first : last + 1])

    def _calc_row_span(self, row: list[str]) -> int:
        """
        行内で実際に使われている列幅を返す。
        シート全体の列幅ではなく、その行自身の密度計算に使う。
        """
        try:
            first = next(index for index, cell in enumerate(row) if cell != "")
            last = max(index for index, cell in enumerate(row) if cell != "")
        except (StopIteration, ValueError):
            return 0

        return last - first + 1

    def _looks_like_heading(self, text: str) -> bool:
        """
        LLM 向けに意味のある短いラベルだけを見出しとして扱う。
        長文や注記は段落へ降格する。
        """
        normalized = text.strip()
        if not normalized:
            return False
        if len(normalized) > self.MAX_HEADING_LENGTH:
            return False
        if any(token in normalized for token in ("。", "<br>", r"\|", ":", "：")):
            return False
        return True

    def _render_text_block(self, text: str) -> str:
        """1 セル相当の意味ブロックを見出しか段落として整形する。"""
        if self._looks_like_heading(text):
            return f"## {text}"
        return text

    def _should_skip_text_block(
        self,
        text: str,
        last_text_block: str | None,
        previous_kv_keys: set[str],
    ) -> bool:
        """
        結合セルの多行展開などで生じる近接重複を抑制する。
        """
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
        """
        表ではなく属性列挙として読むべき行を判定する。
        """
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
        """
        末尾の完全空列を除外して有効列数を返す。
        方眼紙は列数が非常に多いが、大半が空。
        """
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
    ) -> tuple[str, ChunkMeta]:
        """
        バッファされたテーブル行を Markdown テーブルとして出力。
        先頭行をヘッダーとして使用。
        """
        if not buffer:
            return "", ChunkMeta(source_file=file_path, content_type=ContentType.TABLE)

        table_cols = self._calc_effective_cols(buffer)
        if table_cols == 0:
            return "", ChunkMeta(source_file=file_path, content_type=ContentType.TABLE)

        trimmed_buffer = [row[:table_cols] for row in buffer]
        headers = trimmed_buffer[0]  # 先頭行 = ヘッダー
        data_rows = trimmed_buffer[1:] if len(trimmed_buffer) > 1 else []
        md = MarkdownEscaper.make_table(headers, data_rows)
        col_start = get_column_letter(1)
        col_end = get_column_letter(table_cols)
        cell_range = f"{col_start}{start_row + 1}:{col_end}{end_row + 1}"
        chunk = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.TABLE,
            sheet_name=sheet_name,
            cell_range=cell_range,
        )
        return md, chunk

    def _render_kv_row(self, row: list[str]) -> tuple[str, set[str]]:
        """
        疎な行を LLM が読みやすい箇条書き KV 形式に変換。
        """
        if not row:
            return "", set()
        parts: list[str] = []
        keys: set[str] = set()
        # ペアで処理
        i = 0
        while i < len(row):
            if i + 1 < len(row):
                key = MarkdownEscaper.escape_cell(row[i])
                value = MarkdownEscaper.escape_cell(row[i + 1])
                parts.append(f"- **{key}:** {value}")
                keys.add(key)
                i += 2
            else:
                # 余り1個 → 単独テキスト
                parts.append(f"- {MarkdownEscaper.escape_cell(row[i])}")
                i += 1
        return "\n".join(parts), keys

    def _extract_shapes_and_comments(self, ws: Worksheet) -> str:
        """
        シート内のコメントを抽出。
        Note: openpyxl は AutoShape / TextBox の完全な抽出が限定的。
        TODO: VLM(Vision Language Model)による画像解析で補完予定。
        """
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
