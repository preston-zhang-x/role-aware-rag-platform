"""
日本式 Excel 仕様書の専門パーサー。
三大戦略で「方眼紙Excel」を LLM が理解しやすい Markdown に変換する：
1. グローバルコンテキスト注入 (Context Injection)     → シート名を # 見出しに
2. 結合セル解構と展開 (Merged Cells)       → NULL穴を廃止
3. ハイブリッドレイアウトヒューリスティック走査 (Heuristic)   → KV / Table を自動判別
"""

import re
from dataclasses import dataclass
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


@dataclass(frozen=True)
class RowCell:
    """行内の単一セル情報を表現する不変オブジェクト。

    Attributes:
        text: セルの内容テキスト（マークダウンエスケープ済み）
        start_col: セルの開始列インデックス（0ベース）
        end_col: セルの終了列インデックス（0ベース）
    """

    text: str
    start_col: int
    end_col: int

    @property
    def col_span(self) -> int:
        return self.end_col - self.start_col + 1


@dataclass(frozen=True)
class RowProfile:
    """行の全体的なプロファイル（複数セル、配置、構造情報）。

    Attributes:
        row_index: シート内の行番号（0ベース）
        raw_row: 行の生データ（全列分の値）
        cells: 処理済みセルオブジェクトのリスト
    """

    row_index: int
    raw_row: list[str]
    cells: list[RowCell]


class JapaneseExcelParser(BaseParser):
    """
    日本式 Excel 仕様書に特化したパーサー。
    結合セル、複雑なレイアウト、KV形式とテーブルのハイブリッド構造に対応。
    """

    # ─── ハイパーパラメータ定義 ───
    MAX_HEADING_LENGTH = 48  # 見出しとして扱うテキストの最大文字数
    MIN_TABLE_ROWS = 2  # テーブルと判定するための最小行数
    MAX_FORM_ROW_CELLS = 10  # KV形式行として扱う最大セル数
    NOISE_HEADING_PATTERN = re.compile(
        r"^[\s()\[\]{}0-9０-９.．-]+$"
    )  # ノイズ見出しパターン（進捗番号など）

    # ─── コンストラクタ ───
    def __init__(self, density_threshold: float = 0.5):
        """
        初期化メソッド。

        Args:
            density_threshold: 行密度の閾値（0.0～1.0）。
                これを超えるとテーブル行、下回るとKV行と判定。
                デフォルト 0.5 = 50%以上の列にデータがあればテーブル扱い。
        """
        self.density_threshold = density_threshold

    # ─── BaseParser インターフェース実装 ───
    def can_handle(self, file_path: str) -> bool:
        """拡張子で判定: .xlsx, .xlsm"""
        suffix = Path(file_path).suffix.lower()
        return suffix in {".xlsx", ".xlsm"}

    def parse(self, file_path: str) -> ParseResult:
        """
        メインエントリーポイント。ファイル全体を Markdown に変換。

        Args:
            file_path: パース対象のExcelファイルのパス

        Returns:
            ParseResult: 抽出されたマークダウンテキスト、チャンク、警告のセット

        Raises:
            ParseError: ファイルが見つからない、または読み込みに失敗した場合
        """
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"ファイルが見つかりません: {file_path}", file_path)

        all_chunks: list[ChunkMeta] = []
        all_warnings: list[str] = []
        full_text = ""

        # ── 公式の二重読み取り战略 ──
        # data_only=True:  キャッシュされた計算結果を読む（ユーザーに見える値）
        # data_only=False: 数式そのものを読む（元の入力式）
        # この二重読み取りにより、キャッシュ古い場合でも数式が保持される
        try:
            wb_cached = openpyxl.load_workbook(file_path, data_only=True)
            wb_formula = openpyxl.load_workbook(file_path, data_only=False)
        except Exception as exc:
            raise ParseError(f"Excelファイルの読み込みに失敗: {exc}", file_path)

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
                full_text, _ = self._append_section(full_text, f"# {sheet_name}")

                grid, broadcast_cells, merge_spans = self._build_grid_with_merged_cells(
                    ws_cached,
                    ws_formula,
                    all_warnings,
                )
                if not grid:
                    full_text, _ = self._append_section(full_text, "_(空のシート)_")
                    continue

                section_md, section_chunks = self._heuristic_scan(
                    grid,
                    file_path,
                    sheet_name,
                    broadcast_cells,
                    merge_spans,
                )
                if section_md:
                    full_text, section_start = self._append_section(full_text, section_md)
                    if section_start is not None:
                        for chunk in section_chunks:
                            chunk.char_start += section_start
                            chunk.char_end += section_start
                all_chunks.extend(section_chunks)

                # ── TextBox / コメントの抽出 ──
                shapes_md = self._extract_shapes_and_comments(ws_cached)
                if shapes_md:
                    full_text, _ = self._append_section(full_text, shapes_md)

        finally:
            wb_cached.close()
            wb_formula.close()

        text = full_text + "\n" if full_text else ""
        return ParseResult(text=text, chunks=all_chunks, warnings=all_warnings)

    def _append_section(
        self,
        full_text: str,
        section: str,
    ) -> tuple[str, int | None]:
        """最終Markdownへセクションを追加し、その開始位置を返す。"""
        normalized = section.strip()
        if not normalized:
            return full_text, None

        separator = "\n\n" if full_text else ""
        start = len(full_text) + len(separator)
        return f"{full_text}{separator}{normalized}", start

    # ═══════════════════════════════════════════════
    # 戦略2: 結合セル解構と広播
    # ═══════════════════════════════════════════════
    def _build_grid_with_merged_cells(
        self,
        ws_cached: Worksheet,
        ws_formula: Worksheet,
        warnings: list[str],
    ) -> tuple[
        list[list[str]], set[tuple[int, int]], dict[tuple[int, int], tuple[int, int]]
    ]:
        """結合セルを展開・解構してフラットな二次元グリッドを構築。

        Returns:
            grid: 全セル値のフラット二次元リスト
            broadcast_cells: 結合セルから広播されたセルの座標セット
            merge_spans: （アンカー座標 -> (行数, 列数)）のマッピング
        """
        # ─── グリッドの初期化 ───
        if ws_cached.max_row is None or ws_cached.max_column is None:
            # シートが完全に空の場合は空のグリッドを返す
            return [], set(), {}

        max_row = ws_cached.max_row
        max_col = ws_cached.max_column
        # 全セルを" "で初期化したフラットグリッドを作成
        grid: list[list[str]] = [["" for _ in range(max_col)] for _ in range(max_row)]

        # ── Step B: 通常セルの値を読み込む ──
        for row_idx in range(1, max_row + 1):
            for col_idx in range(1, max_col + 1):
                grid[row_idx - 1][col_idx - 1] = self._read_cell_value(
                    ws_cached.cell(row=row_idx, column=col_idx),
                    ws_formula.cell(row=row_idx, column=col_idx),
                    warnings,
                )

        # ─── 結合セルの処理 ───
        broadcast_cells: set[tuple[int, int]] = set()  # 結合セルから値が広播されたセル
        merge_spans: dict[tuple[int, int], tuple[int, int]] = {}  # 結合セルのメタデータ
        for merged_range in ws_cached.merged_cells.ranges:
            # アンカー（結合セルの左上）を基準に行・列スパンを記録
            anchor = (merged_range.min_row - 1, merged_range.min_col - 1)
            merge_spans[anchor] = (
                merged_range.max_row - merged_range.min_row + 1,  # 行数
                merged_range.max_col - merged_range.min_col + 1,  # 列数
            )
            # 結合セル範囲内の全セルを走査してクリア
            for row_idx in range(merged_range.min_row, merged_range.max_row + 1):
                for col_idx in range(merged_range.min_col, merged_range.max_col + 1):
                    if (row_idx - 1, col_idx - 1) != anchor:
                        broadcast_cells.add((row_idx - 1, col_idx - 1))  # 広播セル記録
                        grid[row_idx - 1][col_idx - 1] = ""  # グリッドをクリア

            warnings.append(
                f"{ParserWarning.MERGED_CELL_BROADCAST.value}: {merged_range}"
            )

        return grid, broadcast_cells, merge_spans

    def _read_cell_value(
        self,
        cached_cell: CellLike,
        formula_cell: CellLike,
        warnings: list[str],
    ) -> str:
        """
        セル値の二重読み取り戦略を実装。
        キャッシュ値（計算済み結果）優先、なければ数式テキストをフォールバック。

        Args:
            cached_cell: data_only=True で読み込んだセル（計算結果）
            formula_cell: data_only=False で読み込んだセル（数式）
            warnings: 警告メッセージを追記するリスト

        Returns:
            セルの値を文字列化したもの
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
        merge_spans: dict[tuple[int, int], tuple[int, int]],
    ) -> tuple[str, list[ChunkMeta]]:
        """启发式走査：テーブル vs KV形式などの構造を判定して適切に分割・レンダリング。

        このメソッドはグリッドを上から順に走査し、各行の構造（テキスト、KV、テーブル）
        を自動判定し、対応するマークダウンにレンダリングします。

        Returns:
            markdown: Markdown形式の文字列
            chunks: 抽出されたメタデータチャンク
        """
        del broadcast_cells

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
                block = self._render_text_row(
                    row, file_path, sheet_name, last_text_block
                )
                if block is not None:
                    markdown_parts.append(block[0])
                    chunks.append(block[1])
                    last_text_block = block[2]
                index += 1
                continue

            table_len = self._detect_table_length(row_profiles[index:])
            if table_len:
                table_rows = row_profiles[index : index + table_len]
                table_md, chunk = self._flush_table(
                    table_rows,
                    file_path,
                    sheet_name,
                )
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
        """セクション内の各チャンクに相対的な文字位置を付与する。"""
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
            if (
                cells
                and cells[-1].text == cell.text
                and cells[-1].end_col + 1 >= cell.start_col
            ):
                cells[-1] = RowCell(
                    text=cell.text,
                    start_col=cells[-1].start_col,
                    end_col=max(cells[-1].end_col, cell.end_col),
                )
                continue
            cells.append(cell)
        return RowProfile(row_index=row_idx, raw_row=row, cells=cells)

    def _detect_table_length(self, rows: list[RowProfile]) -> int:
        """行グループの先頭からテーブル構造が続く行数を検出。

        贪心アルゴリズム：最初の行から延長を試し、テーブル性質が失われた時点で終了。

        Args:
            rows: 対象となるRowProfileのリスト

        Returns:
            連続するテーブル行の数（テーブルでない場合は0）
        """
        if len(rows) < self.MIN_TABLE_ROWS:
            return 0

        max_length = 0
        for end in range(self.MIN_TABLE_ROWS, len(rows) + 1):
            candidate = rows[:end]
            if self._looks_like_table_block(candidate):
                max_length = end  # テーブル性質が保全。候補を延長
                continue
            if max_length:
                break  # テーブル性質が失われた→終了
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
            and first_cells[0].col_span >= 4
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
            return len(shared_columns) >= 3 and shared_density >= 0.9

        return len(shared_columns) >= 3 and average_width >= 3

    def _has_structured_merged_columns(self, rows: list[RowProfile]) -> bool:
        sample_rows = rows[: min(3, len(rows))]
        if len(sample_rows) < 2:
            return False

        if min(len(row.cells) for row in sample_rows) < 4:
            return False

        if not any(cell.col_span > 1 for row in sample_rows for cell in row.cells):
            return False

        if self._looks_like_merged_kv_pairs(sample_rows):
            return False

        header_positions = tuple(cell.start_col for cell in sample_rows[0].cells)
        if len(header_positions) < 4:
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
                if key_cell.col_span > 2:
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

        chunk = ChunkMeta(
            source_file=file_path,
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
        """
        LLM 向けに意味のある短いラベルだけを見出しとして扱う。
        長文や注記は段落へ降格する。
        """
        normalized = text.strip()
        if not normalized or len(normalized) > self.MAX_HEADING_LENGTH:
            return False
        if self.NOISE_HEADING_PATTERN.fullmatch(normalized):
            return False
        if any(token in normalized for token in ("。", "<br>", r"\|", ":", "：")):
            return False
        return True

    def _render_text_block(self, text: str) -> str:
        """1 セル相当の意味ブロックを見出しか段落として整形する。"""
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
                parts.append(f"- **{values[i]}:** {values[i + 1]}")
                i += 2
                continue
            parts.append(f"- {values[i]}")
            i += 1

        chunk = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.KEY_VALUE,
            sheet_name=sheet_name,
            cell_range=f"row {row.row_index + 1}",
        )
        return "\n".join(parts), chunk

    def _should_drop_leading_context(
        self,
        row: RowProfile,
        next_row: RowProfile | None,
    ) -> bool:
        if len(row.cells) < 5 or len(row.cells) % 2 == 0:
            return False

        first = row.cells[0]
        if first.col_span < 3:
            return False

        if next_row and next_row.cells and next_row.cells[0].text == first.text:
            return True

        return first.col_span >= max(cell.col_span for cell in row.cells[1:])

    def _calc_effective_cols(self, grid: list[list[str]]) -> int:
        """末尾の完全空列を除外して有効データが存在する列番号を返す。

        日本の方眼紙Excelはしばしば1000列以上の定義を持つが、
        実際のデータは最初の20～50列程度。
        この関数は右側の不要な空列をカット することでパフォーマンスを改善。

        Returns:
            データが存在する最大列番号 + 1（0ベース）
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
        rows: list[RowProfile],
        file_path: str,
        sheet_name: str,
    ) -> tuple[str, ChunkMeta]:
        """テーブル行グループをマークダウン形式に統合・レンダリング。

        重複行の除去、アクティブ列の圧縮、見出しと本体の分離を行います。

        Args:
            rows: テーブル構造と判定された連続するRowProfile群
            file_path: ソースファイル名（メタデータ用）
            sheet_name: シート名（メタデータ用）

        Returns:
            markdown: Markdown表形式の文字列
            chunk: チャンクメタデータ
        """
        if not rows:
            return "", ChunkMeta(source_file=file_path, content_type=ContentType.TABLE)

        active_columns = sorted({cell.start_col for row in rows for cell in row.cells})
        if not active_columns:
            return "", ChunkMeta(source_file=file_path, content_type=ContentType.TABLE)

        compressed_rows = [
            [row.raw_row[col_idx] for col_idx in active_columns] for row in rows
        ]
        deduped_rows = self._dedupe_consecutive_rows(compressed_rows)
        if not deduped_rows:
            return "", ChunkMeta(source_file=file_path, content_type=ContentType.TABLE)

        headers = deduped_rows[0]
        data_rows = deduped_rows[1:]
        markdown = MarkdownEscaper.make_table(headers, data_rows)

        col_start = get_column_letter(active_columns[0] + 1)
        col_end = get_column_letter(active_columns[-1] + 1)
        cell_range = (
            f"{col_start}{rows[0].row_index + 1}:{col_end}{rows[-1].row_index + 1}"
        )
        chunk = ChunkMeta(
            source_file=file_path,
            content_type=ContentType.TABLE,
            sheet_name=sheet_name,
            cell_range=cell_range,
        )
        return markdown, chunk

    def _dedupe_consecutive_rows(self, rows: list[list[str]]) -> list[list[str]]:
        deduped: list[list[str]] = []
        for row in rows:
            escaped = [MarkdownEscaper.escape_cell(cell) for cell in row]
            if all(cell == "" for cell in escaped):
                continue
            if deduped and escaped == deduped[-1]:
                continue
            deduped.append(escaped)
        return deduped

    def _extract_shapes_and_comments(self, ws: Worksheet) -> str:
        """シート内セルのコメント（メモ）を抽出してマークダウンに変換。

        openpyxl の制限:
        - 通常のコメント（セルメモ）は抽出可能
        - AutoShape / TextBox などの自由配置テキストは限定的

        TODO:
            VLM（Vision Language Model）による画像・図形解析で補完予定。
            例：テキストボックス、矢印図形、フローチャートなど

        Returns:
            コメントを列挙したマークダウン（コメントがない場合は空文字列）
        """
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
