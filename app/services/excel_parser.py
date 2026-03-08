"""
日本式 Excel 仕様書の専門パーサー。
三大戦略で「方眼紙Excel」を LLM が理解しやすい Markdown に変換する：
1. 全局上下文注入 (Context Injection)     → Sheet名を # 見出しに
2. 結合セル解構と広播 (Merged Cells)       → None空洞を消滅
3. 混合レイアウト启发式扫描 (Heuristic)   → KV / Table を自動判別
"""

from pathlib import Path

import openpyxl
from openpyxl.cell.cell import Cell
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


class JapaneseExcelParser(BaseParser):
    """
    日本式 Excel 仕様書に特化したパーサー。
    """

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
                markdown_sections.append(f"# {sheet_name}\n")

                # ── 戦略2: 結合セルの解構と広播 ──
                grid = self._build_grid_with_merged_cells(
                    ws_cached, ws_formula, all_warnings
                )
                if not grid:
                    markdown_sections.append("_(空のシート)_\n")
                    continue

                # ── 戦略3: 启发式扫描でKV/テーブルを判別 ──
                section_md, section_chunks = self._heuristic_scan(
                    grid, file_path, sheet_name
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
            text="\n".join(markdown_sections),
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
    ) -> list[list[str]]:
        """
        ワークシートの全セルを2Dリスト(grid)に読み込む。
        結合セルの値を全子セルに広播填充する。
        """
        if ws_cached.max_row is None or ws_cached.max_column is None:
            return []

        max_row = ws_cached.max_row
        max_col = ws_cached.max_column

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

            warnings.append(
                f"{ParserWarning.MERGED_CELL_BROADCAST.value}: {merged_range}"
            )
        return grid

    def _read_cell_value(
        self,
        cached_cell: Cell,
        formula_cell: Cell,
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

        for row_idx, row in enumerate(grid):
            # 有効列のみ切り出し
            effective_row = row[:effective_cols]

            # 空行判定
            if all(cell == "" for cell in effective_row):
                # バッファにテーブルが溜まっていたらフラッシュ
                if table_buffer:
                    md, chunk = self._flush_table(
                        table_buffer,
                        table_start_row,
                        row_idx - 1,
                        file_path,
                        sheet_name,
                        effective_cols,
                    )
                    markdown_parts.append(md)
                    chunks.append(chunk)
                    table_buffer = []
                continue
            # ── 密度計算 ──
            non_empty = sum(1 for cell in effective_row if cell != "")
            density = non_empty / effective_cols

            if density < self.density_threshold:
                # ── 離散モード → KV ──
                # まずバッファフラッシュ
                if table_buffer:
                    md, chunk = self._flush_table(
                        table_buffer,
                        table_start_row,
                        row_idx - 1,
                        file_path,
                        sheet_name,
                        effective_cols,
                    )
                    markdown_parts.append(md)
                    chunks.append(chunk)
                    table_buffer = []

                kv_md = self._render_kv_row(effective_row)
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
            else:
                # ── 連続モード → テーブルバッファに追加 ──
                if not table_buffer:
                    table_start_row = row_idx
                table_buffer.append(effective_row)

        # ループ終了後、残りバッファをフラッシュ
        if table_buffer:
            md, chunk = self._flush_table(
                table_buffer,
                table_start_row,
                len(grid) - 1,
                file_path,
                sheet_name,
                effective_cols,
            )
            markdown_parts.append(md)
            chunks.append(chunk)

        return "\n".join(markdown_parts) + "\n", chunks

    # ═══════════════════════════════════════════════
    # ヘルパーメソッド群
    # ═══════════════════════════════════════════════

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
        headers = buffer[0]  # 先頭行 = ヘッダー
        data_rows = buffer[1:] if len(buffer) > 1 else []
        md = MarkdownEscaper.make_table(headers, data_rows)
        col_start = get_column_letter(1)
        col_end = get_column_letter(effective_cols)
        cell_range = f"{col_start}{start_row + 1}:{col_end}{end_row + 1}"
        chunk = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.TABLE,
            sheet_name=sheet_name,
            cell_range=cell_range,
        )
        return md + "\n", chunk

    def _render_kv_row(self, row: list[str]) -> str:
        """
        疎な行を **Key:** Value 形式に変換。
        """
        non_empty = [cell for cell in row if cell != ""]
        if not non_empty:
            return ""
        parts: list[str] = []
        # ペアで処理
        i = 0
        while i < len(non_empty):
            if i + 1 < len(non_empty):
                key = MarkdownEscaper.escape_cell(non_empty[i])
                value = MarkdownEscaper.escape_cell(non_empty[i + 1])
                parts.append(f"**{key}:** {value}")
                i += 2
            else:
                # 余り1個 → 単独テキスト
                parts.append(MarkdownEscaper.escape_cell(non_empty[i]))
                i += 1
        return "  \n".join(parts)  # Markdown のソフト改行（末尾2スペース）

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
                    coord = f"{get_column_letter(cell.column)}{cell.row}"
                    comment_text = MarkdownEscaper.escape_cell(cell.comment.text)
                    comments_md.append(f"- **[{coord}]** {comment_text}")
        if not comments_md:
            return ""
        return "\n### コメント・注記\n\n" + "\n".join(comments_md) + "\n"
