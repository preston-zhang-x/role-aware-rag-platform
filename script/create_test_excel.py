import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


ROOT_DIR = Path(__file__).resolve().parent.parent
PARSER_PATH = ROOT_DIR / "app" / "services" / "excel_parser.py"
PARSE_RESULT_PATH = ROOT_DIR / "app" / "services" / "parse_result.py"
OUTPUT_PATH = ROOT_DIR / "data" / "fixtures" / "japanese_spec.xlsx"
CellValue = str | int | float | bool | None


@dataclass(frozen=True)
class ParameterInfo:
    name: str
    type_name: str
    default_text: str


@dataclass(frozen=True)
class ParserMethodInfo:
    name: str
    line_no: int
    return_type: str
    doc_summary: str
    parameters: list[ParameterInfo]


@dataclass(frozen=True)
class WarningInfo:
    name: str
    value: str


@dataclass(frozen=True)
class MethodDesignInfo:
    phase: str
    purpose: str
    called_by: str
    calls: str
    warning_behavior: str
    return_description: str
    note: str
    parameter_descriptions: dict[str, str]


METHOD_DESIGN: dict[str, MethodDesignInfo] = {
    "__init__": MethodDesignInfo(
        phase="初期化",
        purpose="行密度しきい値を保持する。",
        called_by="DocumentLoader / 直接生成 / テスト",
        calls="なし",
        warning_behavior="なし",
        return_description="インスタンス状態を初期化する。",
        note="density_threshold は _heuristic_scan の KV / Table 分岐に使用する。",
        parameter_descriptions={
            "density_threshold": "非空セル密度の境界値。0.5 未満を KV、以上を Table とみなす。",
        },
    ),
    "can_handle": MethodDesignInfo(
        phase="入口判定",
        purpose="拡張子ベースで処理対象可否を返す。",
        called_by="DocumentLoader.load",
        calls="Path.suffix.lower",
        warning_behavior="なし",
        return_description=".xlsx / .xlsm を True として返す。",
        note="内容解析は行わず、軽量に振り分ける。",
        parameter_descriptions={
            "file_path": "判定対象ファイルのパス。",
        },
    ),
    "parse": MethodDesignInfo(
        phase="メイン処理",
        purpose="Workbook 二重読込、Sheet 走査、Markdown / Chunk / Warning 集約を行う。",
        called_by="DocumentLoader.load / 直接呼出し",
        calls="_build_grid_with_merged_cells / _heuristic_scan / _extract_shapes_and_comments / openpyxl.load_workbook",
        warning_behavior="HIDDEN_SHEET_SKIPPED と下位 warning を集約する。",
        return_description="ParseResult(text, chunks, warnings) を返す。",
        note="data_only=True と False を併用して数式キャッシュと原式の両方を扱う。",
        parameter_descriptions={
            "file_path": "解析対象 Excel ファイルのパス。",
        },
    ),
    "_build_grid_with_merged_cells": MethodDesignInfo(
        phase="セル正規化",
        purpose="Worksheet 全体を文字列 2D grid に変換し、結合セルをブロードキャストする。",
        called_by="parse",
        calls="_read_cell_value",
        warning_behavior="MERGED_CELL_BROADCAST を範囲単位で追加する。",
        return_description="結合セル展開済みの 2D grid を返す。",
        note="openpyxl は 1-based、grid は 0-based の差を吸収する。",
        parameter_descriptions={
            "ws_cached": "data_only=True 側の Worksheet。",
            "ws_formula": "data_only=False 側の Worksheet。",
            "warnings": "warning 集約先リスト。",
        },
    ),
    "_read_cell_value": MethodDesignInfo(
        phase="セル正規化",
        purpose="キャッシュ値・数式・空セルを三分岐で文字列化する。",
        called_by="_build_grid_with_merged_cells",
        calls="str / startswith",
        warning_behavior="FORMULA_NO_CACHE を必要時のみ追加する。",
        return_description="Markdown 化に使う正規化済みセル文字列を返す。",
        note="キャッシュが無く数式だけある場合は `formula: ...` 形式で保持する。",
        parameter_descriptions={
            "cached_cell": "計算済み値の取得元。",
            "formula_cell": "原数式の取得元。",
            "warnings": "数式 warning の追加先。",
        },
    ),
    "_heuristic_scan": MethodDesignInfo(
        phase="ヒューリスティック",
        purpose="行密度で KV / Table を切り替え、Markdown と Chunk を同時生成する。",
        called_by="parse",
        calls="_calc_effective_cols / _flush_table / _render_kv_row / ChunkMeta",
        warning_behavior="warning は追加しないが chunk 種別を出し分ける。",
        return_description="Sheet 単位の Markdown 片と Chunk 一覧を返す。",
        note="空行に遭遇した時点で table buffer を flush する。",
        parameter_descriptions={
            "grid": "結合セル展開済みの 2D 文字列グリッド。",
            "file_path": "ChunkMeta.source_file 用パス。",
            "sheet_name": "ChunkMeta.sheet_name 用。",
        },
    ),
    "_calc_effective_cols": MethodDesignInfo(
        phase="ヒューリスティック補助",
        purpose="末尾空列を削って実列数を返す。",
        called_by="_heuristic_scan",
        calls="any",
        warning_behavior="なし",
        return_description="密度計算に使う有効列数を返す。",
        note="日本式シートの右側余白列を無視する。",
        parameter_descriptions={
            "grid": "Sheet 全体の 2D grid。",
        },
    ),
    "_flush_table": MethodDesignInfo(
        phase="テーブル出力",
        purpose="table buffer を Markdown テーブルと Table Chunk に変換する。",
        called_by="_heuristic_scan",
        calls="MarkdownEscaper.make_table / get_column_letter / ChunkMeta",
        warning_behavior="なし",
        return_description="Markdown テーブルと ChunkMeta のペアを返す。",
        note="先頭行をヘッダとして扱う前提。",
        parameter_descriptions={
            "buffer": "連続した高密度行のバッファ。",
            "start_row": "buffer 開始行の 0-based index。",
            "end_row": "buffer 終了行の 0-based index。",
            "file_path": "ChunkMeta.source_file に設定する値。",
            "sheet_name": "ChunkMeta.sheet_name に設定する値。",
            "effective_cols": "右端空列除去後の列数。",
        },
    ),
    "_render_kv_row": MethodDesignInfo(
        phase="KV出力",
        purpose="疎な行を **Key:** Value 形式の Markdown に変換する。",
        called_by="_heuristic_scan",
        calls="MarkdownEscaper.escape_cell",
        warning_behavior="なし",
        return_description="1 行分の KV Markdown を返す。",
        note="奇数個の末尾セルは単独テキストとして扱う。",
        parameter_descriptions={
            "row": "1 行分の文字列配列。",
        },
    ),
    "_extract_shapes_and_comments": MethodDesignInfo(
        phase="注記抽出",
        purpose="Comment を Markdown 箇条書きに変換する。",
        called_by="parse",
        calls="Worksheet.iter_rows / MarkdownEscaper.escape_cell / get_column_letter",
        warning_behavior="現状 warning 追加は無し。",
        return_description="Comment セクション Markdown。無ければ空文字。",
        note="TextBox は未対応、Comment 抽出が主対象。",
        parameter_descriptions={
            "ws": "コメント走査対象 Worksheet。",
        },
    ),
}


def _annotation_text(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else "-"


def _string_constant(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ast.unparse(node)


def _load_parser_methods() -> list[ParserMethodInfo]:
    module = ast.parse(PARSER_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "JapaneseExcelParser":
            methods: list[ParserMethodInfo] = []
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                doc = ast.get_docstring(item) or ""
                summary = doc.strip().splitlines()[0] if doc.strip() else "-"
                positional = item.args.args[1:]
                defaults = [None] * (len(positional) - len(item.args.defaults)) + list(
                    item.args.defaults
                )
                parameters: list[ParameterInfo] = []
                for arg, default in zip(positional, defaults):
                    parameters.append(
                        ParameterInfo(
                            name=arg.arg,
                            type_name=_annotation_text(arg.annotation),
                            default_text="-" if default is None else ast.unparse(default),
                        )
                    )
                methods.append(
                    ParserMethodInfo(
                        name=item.name,
                        line_no=item.lineno,
                        return_type=_annotation_text(item.returns),
                        doc_summary=summary,
                        parameters=parameters,
                    )
                )
            return methods
    raise ValueError("JapaneseExcelParser not found in excel_parser.py")


def _load_warning_definitions() -> list[WarningInfo]:
    module = ast.parse(PARSE_RESULT_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "ParserWarning":
            warnings: list[WarningInfo] = []
            for item in node.body:
                if not isinstance(item, ast.Assign) or len(item.targets) != 1:
                    continue
                target = item.targets[0]
                if isinstance(target, ast.Name):
                    warnings.append(
                        WarningInfo(name=target.id, value=_string_constant(item.value))
                    )
            return warnings
    raise ValueError("ParserWarning not found in parse_result.py")


def _active_sheet(workbook: Workbook) -> Worksheet:
    worksheet = workbook.active
    assert worksheet is not None
    return worksheet


def _style_cell(
    cell: Cell,
    *,
    font: Font | None = None,
    fill: PatternFill | None = None,
    alignment: Alignment | None = None,
) -> None:
    cell.font = font or Font(name="Meiryo", size=10)
    cell.fill = fill or PatternFill(fill_type=None)
    cell.alignment = alignment or Alignment(vertical="top", wrap_text=True)
    cell.border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )


def _merged_block(
    worksheet: Worksheet,
    start_row: int,
    start_col: int,
    end_row: int,
    end_col: int,
    value: CellValue,
    *,
    font: Font | None = None,
    fill: PatternFill | None = None,
    alignment: Alignment | None = None,
) -> None:
    worksheet.merge_cells(
        start_row=start_row,
        start_column=start_col,
        end_row=end_row,
        end_column=end_col,
    )
    cell = worksheet.cell(row=start_row, column=start_col, value=value)
    _style_cell(
        cell,
        font=font,
        fill=fill,
        alignment=alignment or Alignment(horizontal="center", vertical="center", wrap_text=True),
    )


def _header_row(worksheet: Worksheet, row_index: int, headers: Sequence[str]) -> None:
    for column_index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=row_index, column=column_index, value=header)
        _style_cell(
            cell,
            font=Font(name="Meiryo", bold=True, size=10, color="FFFFFF"),
            fill=PatternFill("solid", fgColor="4472C4"),
            alignment=Alignment(horizontal="center", vertical="center", wrap_text=True),
        )


def _apply_table_header(cell: Cell) -> None:
    cell.font = Font(name="Meiryo", bold=True, size=10, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4472C4")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )


def _apply_table_value(cell: Cell) -> None:
    cell.font = Font(name="Meiryo", size=10)
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    cell.border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )


def _set_widths(worksheet: Worksheet, widths: Iterable[int]) -> None:
    for index, width in enumerate(widths, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = width


def _fill_row(worksheet: Worksheet, row_index: int, values: Sequence[CellValue]) -> None:
    for column_index, value in enumerate(values, start=1):
        cell = worksheet.cell(row=row_index, column=column_index, value=value)
        _apply_table_value(cell)


def _build_overview_sheet(workbook: Workbook) -> None:
    worksheet = _active_sheet(workbook)
    worksheet.title = "基本設計"

    worksheet.merge_cells("A1:H1")
    title_cell = worksheet["A1"]
    title_cell.value = "NFTマーケットプレイス 基本設計書"
    title_cell.font = Font(name="Meiryo", bold=True, size=14, color="FFFFFF")
    title_cell.fill = PatternFill("solid", fgColor="2F5496")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    worksheet.row_dimensions[1].height = 28

    metadata = [
        ("プロジェクト名", "NFT Lite Business Platform", "管理番号", "PRJ-2024-001"),
        ("作成者", "田中　太郎", "作成日", "2024-01-15"),
        ("承認者", "鈴木部長", "承認日", "2024-01-20"),
        ("バージョン", "2.1.0", "ステータス", "レビュー完了"),
    ]
    for row_index, (left_key, left_value, right_key, right_value) in enumerate(
        metadata, start=2
    ):
        worksheet[f"A{row_index}"] = left_key
        worksheet[f"B{row_index}"] = left_value
        worksheet[f"E{row_index}"] = right_key
        worksheet[f"F{row_index}"] = right_value

    worksheet.merge_cells("A7:H7")
    worksheet["A7"] = "1. システム概要"
    worksheet["A7"].font = Font(name="Meiryo", bold=True, size=12)
    worksheet["A7"].fill = PatternFill("solid", fgColor="D9E2F3")

    worksheet.merge_cells("A8:H8")
    worksheet["A8"] = (
        "本システムはNFTの出品・購入・管理を行う業務向けプラットフォームです。"
        "Spring Boot と PostgreSQL を中心に構成します。"
    )
    worksheet["A8"].alignment = Alignment(wrap_text=True)
    worksheet.row_dimensions[8].height = 36

    worksheet.merge_cells("A10:H10")
    worksheet["A10"] = "2. 機能一覧"
    worksheet["A10"].font = Font(name="Meiryo", bold=True, size=12)
    worksheet["A10"].fill = PatternFill("solid", fgColor="D9E2F3")

    headers = ["機能ID", "機能名", "カテゴリ", "優先度", "担当", "工数", "進捗", "備考"]
    for column_index, header in enumerate(headers, start=1):
        _apply_table_header(worksheet.cell(row=11, column=column_index, value=header))

    rows = [
        ["F-001", "ログイン", "認証", "高", "佐藤", 3, 100, "MFA対応"],
        ["F-002", "会員登録", "認証", "高", "田中", 4, 90, "招待コード対応"],
        ["F-003", "商品一覧", "UI", "高", "山田", 5, 80, "検索条件あり"],
        ["F-004", "商品詳細", "UI", "中", "山田", 2, 75, "画像ギャラリー"],
        ["F-005", "出品申請", "業務", "高", "高橋", 6, 60, "添付ファイル対応"],
        ["F-006", "管理画面", "管理", "中", "鈴木", 7, 40, "承認フローあり"],
        ["F-007", "通知送信", "バッチ", "中", "伊藤", 3, 50, "Slack連携"],
        ["F-008", "レポート出力", "帳票", "低", "加藤", 2, 20, "CSV対応"],
    ]
    for row_index, row_values in enumerate(rows, start=12):
        _fill_row(worksheet, row_index, row_values)

    total_label_cell = worksheet.cell(row=20, column=5, value="合計")
    total_label_cell.font = Font(name="Meiryo", bold=True, size=10)
    total_formula_cell = worksheet.cell(row=20, column=6, value="=SUM(F12:F19)")
    total_formula_cell.font = Font(name="Meiryo", bold=True, size=10)

    worksheet["F3"].comment = Comment("田中太郎は4月から異動予定です。", "管理者")
    worksheet["H14"].comment = Comment("パイプ | 改行\n全角　スペースを含む。", "レビュー担当")

    worksheet.merge_cells("A22:H22")
    worksheet["A22"] = "補足: パイプ | 改行\n全角　スペース を含むテキスト"
    worksheet["A22"].alignment = Alignment(wrap_text=True)
    worksheet.row_dimensions[22].height = 32

    _set_widths(worksheet, [12, 20, 12, 10, 10, 10, 10, 24])


def _build_database_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("DB定義")
    worksheet.merge_cells("A1:F1")
    worksheet["A1"] = "users テーブル"
    worksheet["A1"].font = Font(name="Meiryo", bold=True, size=12)
    worksheet["A1"].fill = PatternFill("solid", fgColor="D9E2F3")

    headers = ["カラム名", "型", "PK", "NULL", "デフォルト", "説明"]
    for column_index, header in enumerate(headers, start=1):
        _apply_table_header(worksheet.cell(row=3, column=column_index, value=header))

    rows = [
        ["id", "BIGINT", "Y", "N", "AUTO", "ユーザーID"],
        ["email", "VARCHAR(255)", "N", "N", "", "メールアドレス"],
        ["display_name", "VARCHAR(100)", "N", "N", "", "表示名"],
        ["role", "VARCHAR(20)", "N", "N", "viewer", "権限区分"],
    ]
    for row_index, row_values in enumerate(rows, start=4):
        _fill_row(worksheet, row_index, row_values)

    _set_widths(worksheet, [18, 18, 8, 8, 14, 24])


def _build_api_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("API仕様")
    worksheet.merge_cells("A1:E1")
    worksheet["A1"] = "公開 API 一覧"
    worksheet["A1"].font = Font(name="Meiryo", bold=True, size=12)
    worksheet["A1"].fill = PatternFill("solid", fgColor="D9E2F3")

    headers = ["エンドポイント", "メソッド", "説明", "認証", "レスポンス"]
    for column_index, header in enumerate(headers, start=1):
        _apply_table_header(worksheet.cell(row=3, column=column_index, value=header))

    rows = [
        ["/api/auth/login", "POST", "ログイン", "不要", "200 OK"],
        ["/api/users", "GET", "ユーザー一覧", "必須", "200 OK"],
        ["/api/users/{id}", "PUT", "ユーザー更新", "必須", "200 OK"],
        ["/api/reports/export", "GET", "CSV出力", "必須", "202 Accepted"],
    ]
    for row_index, row_values in enumerate(rows, start=4):
        _fill_row(worksheet, row_index, row_values)

    _set_widths(worksheet, [26, 12, 20, 10, 18])


def _build_screen_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("画面設計")
    worksheet.merge_cells("A1:D1")
    worksheet["A1"] = "ログイン画面"
    worksheet["A1"].font = Font(name="Meiryo", bold=True, size=12)
    worksheet["A1"].fill = PatternFill("solid", fgColor="D9E2F3")

    rows = [
        ["項目", "種別", "必須", "備考"],
        ["メールアドレス", "text", "Y", "最大255文字"],
        ["パスワード", "password", "Y", "8文字以上"],
        ["ログインボタン", "button", "-", "Enterキー対応"],
        ["エラーメッセージ", "label", "-", "赤字表示"],
    ]
    for row_index, row_values in enumerate(rows, start=3):
        for column_index, value in enumerate(row_values, start=1):
            cell = worksheet.cell(row=row_index, column=column_index, value=value)
            if row_index == 3:
                _apply_table_header(cell)
            else:
                _apply_table_value(cell)

    worksheet["D7"].comment = Comment("画面遷移図は別シート参照。", "設計者")
    _set_widths(worksheet, [18, 16, 10, 24])


def _build_hidden_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("計算用_非表示")
    worksheet.sheet_state = "hidden"
    worksheet["A1"] = "項目"
    worksheet["B1"] = "値"
    worksheet["A2"] = "原価"
    worksheet["B2"] = 1200
    worksheet["A3"] = "利益率"
    worksheet["B3"] = 0.35
    worksheet["A4"] = "販売価格"
    worksheet["B4"] = "=B2*(1+B3)"


def _build_parser_detail_sheet(
    workbook: Workbook,
    methods: Sequence[ParserMethodInfo],
) -> None:
    worksheet = workbook.create_sheet("ExcelParser詳細")
    _merged_block(
        worksheet,
        1,
        1,
        2,
        12,
        "excel_parser.py 詳細設計",
        font=Font(name="Meiryo", bold=True, size=14, color="FFFFFF"),
        fill=PatternFill("solid", fgColor="1F4E78"),
    )

    _merged_block(worksheet, 4, 1, 4, 3, "ファイル", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    _merged_block(worksheet, 4, 4, 4, 12, str(PARSER_PATH.relative_to(ROOT_DIR)), fill=PatternFill("solid", fgColor="EAF2F8"))
    _merged_block(worksheet, 5, 1, 5, 3, "クラス", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    _merged_block(worksheet, 5, 4, 5, 12, "JapaneseExcelParser", fill=PatternFill("solid", fgColor="EAF2F8"))
    _merged_block(worksheet, 6, 1, 6, 3, "既定しきい値", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    threshold = worksheet.cell(row=6, column=4, value="='設計計算_非表示'!B6")
    _style_cell(threshold, font=Font(name="Meiryo", bold=True, size=10), fill=PatternFill("solid", fgColor="E2F0D9"), alignment=Alignment(horizontal="center", vertical="center"))
    _merged_block(worksheet, 6, 5, 6, 12, "row density が 0.5 未満なら KV、以上なら Table", fill=PatternFill("solid", fgColor="EAF2F8"))

    _merged_block(worksheet, 8, 1, 8, 12, "入出力マトリクス", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    _header_row(
        worksheet,
        9,
        ["区分", "名称", "型", "生成元", "消費先", "意味", "区分", "名称", "型", "生成元", "消費先", "意味"],
    )
    rows = [
        ["入力", "file_path", "str", "DocumentLoader", "parse", "元 Excel パス", "中間", "wb_cached", "Workbook", "openpyxl", "parse", "data_only=True"],
        ["中間", "wb_formula", "Workbook", "openpyxl", "parse", "数式文字列側", "中間", "grid", "list[list[str]]", "_build_grid...", "_heuristic_scan", "結合セル展開済み"],
        ["出力", "ParseResult.text", "str", "parse", "呼出元", "Markdown 本文", "出力", "ParseResult.chunks", "list[ChunkMeta]", "parse", "呼出元", "検索用メタ"],
        ["出力", "ParseResult.warnings", "list[str]", "parse", "呼出元", "warning 集約", "補助", "ParserWarning", "Enum", "parse_result.py", "parse", "warning 種別定義"],
    ]
    for row_index, row_values in enumerate(rows, start=10):
        _fill_row(worksheet, row_index, row_values)

    _merged_block(worksheet, 16, 1, 16, 12, "メソッド一覧", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    _header_row(worksheet, 17, ["No", "メソッド", "行番号", "返却型", "doc summary", "No", "メソッド", "行番号", "返却型", "doc summary", "", ""])
    split = (len(methods) + 1) // 2
    left_methods = methods[:split]
    right_methods = methods[split:]
    max_rows = max(len(left_methods), len(right_methods))
    for index in range(max_rows):
        row_index = 18 + index
        values: list[CellValue] = []
        for group_index, method in enumerate(
            [
                left_methods[index] if index < len(left_methods) else None,
                right_methods[index] if index < len(right_methods) else None,
            ],
            start=1,
        ):
            if method is None:
                values.extend(["", "", "", "", ""])
            else:
                values.extend(
                    [
                        index + 1 if group_index == 1 else split + index + 1,
                        method.name,
                        method.line_no,
                        method.return_type,
                        method.doc_summary,
                    ]
                )
        values.extend(["", ""])
        _fill_row(worksheet, row_index, values)

    worksheet.freeze_panes = "A9"
    _set_widths(worksheet, [12, 24, 10, 24, 30, 12, 24, 10, 24, 30, 6, 6])


def _build_method_matrix_sheet(
    workbook: Workbook,
    methods: Sequence[ParserMethodInfo],
) -> None:
    worksheet = workbook.create_sheet("メソッドマトリクス")
    _merged_block(
        worksheet,
        1,
        1,
        2,
        17,
        "JapaneseExcelParser メソッド詳細マトリクス",
        font=Font(name="Meiryo", bold=True, size=14, color="FFFFFF"),
        fill=PatternFill("solid", fgColor="1F4E78"),
    )
    _header_row(
        worksheet,
        4,
        [
            "工程",
            "メソッド名",
            "公開区分",
            "ソース行",
            "役割",
            "引数No",
            "引数名",
            "型",
            "既定値",
            "引数の意味",
            "返却型",
            "返却値の意味",
            "呼出元",
            "内部呼出",
            "warning / event",
            "設計メモ",
            "doc summary",
        ],
    )

    current_row = 5
    for method in methods:
        design = METHOD_DESIGN[method.name]
        parameters = method.parameters or [
            ParameterInfo(name="(なし)", type_name="-", default_text="-")
        ]
        start_row = current_row
        for index, parameter in enumerate(parameters, start=1):
            row_fill = PatternFill(
                "solid",
                fgColor="F8FBFF" if index % 2 == 0 else "EAF2F8",
            )
            cells = [
                (6, index),
                (7, parameter.name),
                (8, parameter.type_name),
                (9, parameter.default_text),
                (10, design.parameter_descriptions.get(parameter.name, "-")),
            ]
            for column, value in cells:
                cell = worksheet.cell(row=current_row, column=column, value=value)
                _style_cell(cell, fill=row_fill)
            current_row += 1

        end_row = current_row - 1
        visibility = "public" if not method.name.startswith("_") or method.name == "__init__" else "private"
        method_fill = PatternFill(
            "solid",
            fgColor="E2F0D9" if visibility == "public" else "EDEDED",
        )
        merged_values = [
            (1, design.phase),
            (2, method.name),
            (3, visibility),
            (4, method.line_no),
            (5, design.purpose),
            (11, method.return_type),
            (12, design.return_description),
            (13, design.called_by),
            (14, design.calls),
            (15, design.warning_behavior),
            (16, design.note),
            (17, method.doc_summary),
        ]
        for column, value in merged_values:
            worksheet.merge_cells(
                start_row=start_row,
                start_column=column,
                end_row=end_row,
                end_column=column,
            )
            cell = worksheet.cell(row=start_row, column=column, value=value)
            _style_cell(
                cell,
                font=Font(name="Meiryo", bold=True, size=10) if column in {2, 3, 11} else Font(name="Meiryo", size=10),
                fill=method_fill if column <= 5 else PatternFill("solid", fgColor="F4F8FC"),
            )

    worksheet.freeze_panes = "A5"
    worksheet.auto_filter.ref = f"A4:Q{current_row - 1}"
    _set_widths(worksheet, [12, 22, 12, 10, 34, 8, 18, 18, 12, 34, 22, 30, 20, 28, 24, 34, 28])


def _build_sequence_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("処理シーケンス")
    _merged_block(
        worksheet,
        1,
        1,
        2,
        10,
        "parse() 処理シーケンス / スイムレーン",
        font=Font(name="Meiryo", bold=True, size=14, color="FFFFFF"),
        fill=PatternFill("solid", fgColor="1F4E78"),
    )
    _header_row(
        worksheet,
        4,
        ["Step", "呼出元", "parse", "_build_grid", "_read_cell_value", "_heuristic_scan", "_flush_table", "_render_kv_row", "_extract_shapes", "出力"],
    )
    rows = [
        ["1", "DocumentLoader", "ファイル存在確認", "", "", "", "", "", "", ""],
        ["2", "DocumentLoader", "Workbook を data_only / formula で二重ロード", "", "", "", "", "", "", ""],
        ["3", "DocumentLoader", "visible sheet のみ継続", "", "", "", "", "", "", "HIDDEN_SHEET_SKIPPED"],
        ["4", "", "sheet 見出し追加", "grid 初期化", "セル値正規化", "", "", "", "", ""],
        ["5", "", "", "通常セル読込", "cached / formula / empty を判定", "", "", "", "", ""],
        ["6", "", "", "merged range 展開", "", "", "", "", "", "MERGED_CELL_BROADCAST"],
        ["7", "", "", "", "", "effective_cols 算出", "", "", "", ""],
        ["8", "", "", "", "", "行密度算出", "", "", "", ""],
        ["9", "", "", "", "", "疎な行", "", "KV Markdown 生成", "", "KEY_VALUE chunk"],
        ["10", "", "", "", "", "密な行", "table buffer flush", "", "", "TABLE chunk"],
        ["11", "", "comment 抽出", "", "", "", "", "", "comment markdown", ""],
        ["12", "", "ParseResult 組立", "", "", "", "", "", "", "text/chunks/warnings"],
    ]
    for row_index, row_values in enumerate(rows, start=5):
        _fill_row(worksheet, row_index, row_values)

    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [8, 16, 24, 18, 18, 18, 18, 18, 18, 20])


def _build_rule_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("判定ロジック")
    _merged_block(
        worksheet,
        1,
        1,
        2,
        12,
        "ヒューリスティック判定・結合セル・数式フォールバック設計",
        font=Font(name="Meiryo", bold=True, size=14, color="FFFFFF"),
        fill=PatternFill("solid", fgColor="1F4E78"),
    )

    _merged_block(worksheet, 4, 1, 4, 12, "密度判定マトリクス", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    worksheet["B5"] = "しきい値"
    _style_cell(worksheet["B5"], font=Font(name="Meiryo", bold=True, size=10), fill=PatternFill("solid", fgColor="D9E2F3"), alignment=Alignment(horizontal="center", vertical="center"))
    worksheet["C5"] = "='設計計算_非表示'!B6"
    _style_cell(worksheet["C5"], font=Font(name="Meiryo", bold=True, size=10), fill=PatternFill("solid", fgColor="E2F0D9"), alignment=Alignment(horizontal="center", vertical="center"))
    _header_row(worksheet, 6, ["Case", "非空セル数", "有効列数", "密度", "しきい値", "分類", "備考"])
    density_rows = [
        ["R-01", 2, 8, "=B7/C7", "=$C$5", '=IF(D7<E7,"KEY_VALUE","TABLE")', "典型的な作成者 / 日付 / 版数"],
        ["R-02", 4, 8, "=B8/C8", "=$C$5", '=IF(D8<E8,"KEY_VALUE","TABLE")', "境界未満だが情報量は中程度"],
        ["R-03", 5, 8, "=B9/C9", "=$C$5", '=IF(D9<E9,"KEY_VALUE","TABLE")', "0.625 なので TABLE"],
        ["R-04", 8, 8, "=B10/C10", "=$C$5", '=IF(D10<E10,"KEY_VALUE","TABLE")', "フル表データ"],
    ]
    for row_index, row_values in enumerate(density_rows, start=7):
        _fill_row(worksheet, row_index, row_values)

    _merged_block(worksheet, 13, 1, 13, 12, "数式キャッシュ読取ルール", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    _header_row(worksheet, 14, ["Case", "cached_value", "formula_value", "warning", "返却値", "設計意図"])
    formula_rows = [
        ["F-01", "100", "=SUM(A1:A5)", "なし", "100", "キャッシュがあれば最優先"],
        ["F-02", "", "=SUM(A1:A5)", "FORMULA_NO_CACHE", "formula: =SUM(A1:A5)", "計算値が無い場合でも意味を保持"],
        ["F-03", "", "", "なし", "", "完全空セル"],
    ]
    for row_index, row_values in enumerate(formula_rows, start=15):
        _fill_row(worksheet, row_index, row_values)

    _merged_block(worksheet, 20, 1, 20, 12, "結合セルブロードキャスト イメージ", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    worksheet.merge_cells("B22:D22")
    worksheet["B22"] = "元の左上値"
    _style_cell(worksheet["B22"], font=Font(name="Meiryo", bold=True, size=10), fill=PatternFill("solid", fgColor="E2F0D9"), alignment=Alignment(horizontal="center", vertical="center"))
    for row in range(23, 25):
        for col in range(2, 5):
            cell = worksheet.cell(row=row, column=col, value="元の左上値")
            _style_cell(cell, fill=PatternFill("solid", fgColor="EAF2F8"), alignment=Alignment(horizontal="center", vertical="center"))
    worksheet["F22"] = "設計上は merged_range 全域へ同一値を複製する"
    _style_cell(worksheet["F22"], fill=PatternFill("solid", fgColor="FFF2CC"))
    worksheet["F23"] = "warning には MERGED_CELL_BROADCAST を範囲ごとに追加"
    _style_cell(worksheet["F23"], fill=PatternFill("solid", fgColor="FFF2CC"))

    worksheet.freeze_panes = "A6"
    _set_widths(worksheet, [10, 14, 14, 14, 14, 18, 30, 12, 12, 12, 12, 12])


def _build_warning_sheet(workbook: Workbook, warnings: Sequence[WarningInfo]) -> None:
    worksheet = workbook.create_sheet("警告・例外一覧")
    _merged_block(
        worksheet,
        1,
        1,
        2,
        9,
        "warning / exception 一覧",
        font=Font(name="Meiryo", bold=True, size=14, color="FFFFFF"),
        fill=PatternFill("solid", fgColor="1F4E78"),
    )

    _merged_block(worksheet, 4, 1, 4, 9, "ParserWarning 一覧", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    _header_row(worksheet, 5, ["No", "enum 名", "メッセージ", "主な発生箇所", "契機", "ユーザー影響", "優先度", "備考", "関連メソッド"])
    warning_context = {
        "FORMULA_NO_CACHE": ("_read_cell_value", "数式キャッシュ欠落", "数式テキストにフォールバック", "中", "数式意味は保持"),
        "SHAPE_SKIPPED": ("未使用", "図形抽出未対応", "Shape は完全抽出不可", "低", "将来拡張想定"),
        "MERGED_CELL_BROADCAST": ("_build_grid_with_merged_cells", "結合セル展開", "同じ値が全セルへ複製される", "中", "LLM 文脈保持優先"),
        "HIDDEN_SHEET_SKIPPED": ("parse", "非表示シート", "シート本文を出力しない", "中", "warning で痕跡は残す"),
        "SCAN_PAGE_DETECTED": ("未使用", "OCR 対象検知", "現 parser では未使用", "低", "共通 warning 候補"),
        "PARSER_FALLBACK": ("上位 loader", "primary fail", "fallback parser 利用", "高", "DocumentLoader 文脈"),
    }
    for row_index, warning in enumerate(warnings, start=6):
        source, trigger, impact, priority, note = warning_context.get(
            warning.name,
            ("-", "-", "-", "-", "-"),
        )
        _fill_row(
            worksheet,
            row_index,
            [
                row_index - 5,
                warning.name,
                warning.value,
                source,
                trigger,
                impact,
                priority,
                note,
                source,
            ],
        )

    _merged_block(worksheet, 14, 1, 14, 9, "ParseError シナリオ", font=Font(name="Meiryo", bold=True, size=11), fill=PatternFill("solid", fgColor="D9E2F3"))
    _header_row(worksheet, 15, ["No", "例外", "発生条件", "発生箇所", "メッセージ例", "復旧案", "備考", "", ""])
    error_rows = [
        ["1", "ParseError", "file_path が存在しない", "parse", "ファイルが見つかりません", "パス確認", "入口で fail-fast", "", ""],
        ["2", "ParseError", "Workbook 読込失敗", "parse", "Excel ファイルの読込に失敗", "実体 / 形式確認", "openpyxl 例外を内包", "", ""],
    ]
    for row_index, row_values in enumerate(error_rows, start=16):
        _fill_row(worksheet, row_index, row_values)

    _set_widths(worksheet, [8, 22, 38, 22, 20, 24, 10, 18, 18])


def _build_test_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("テスト観点")
    _merged_block(
        worksheet,
        1,
        1,
        2,
        10,
        "excel_parser.py テスト観点一覧",
        font=Font(name="Meiryo", bold=True, size=14, color="FFFFFF"),
        fill=PatternFill("solid", fgColor="1F4E78"),
    )
    _header_row(worksheet, 4, ["観点ID", "入力パターン", "対象メソッド", "期待 Markdown", "期待 Chunk", "期待 warning", "難易度", "備考", "再現シート", "優先度"])
    rows = [
        ["T-001", "通常表", "parse / _heuristic_scan / _flush_table", "Markdown Table", "TABLE", "なし", "中", "最頻ケース", "基本設計", "高"],
        ["T-002", "疎な KV 行", "_heuristic_scan / _render_kv_row", "**Key:** Value", "KEY_VALUE", "なし", "中", "版数 / 作成者", "基本設計", "高"],
        ["T-003", "結合セル", "_build_grid_with_merged_cells", "値が全域へ複製", "TABLE または TEXT", "MERGED_CELL_BROADCAST", "高", "神 Excel の本丸", "判定ロジック", "高"],
        ["T-004", "キャッシュ無し数式", "_read_cell_value", "formula: =...", "TABLE", "FORMULA_NO_CACHE", "高", "Excel 保存状態依存", "計算用_非表示", "高"],
        ["T-005", "非表示シート", "parse", "本文対象外", "なし", "HIDDEN_SHEET_SKIPPED", "中", "warning 集約確認", "計算用_非表示", "中"],
        ["T-006", "コメントあり", "_extract_shapes_and_comments", "### コメント注記", "なし", "なし", "低", "TextBox は未対応", "画面設計", "中"],
        ["T-007", "パイプ / 改行 / 全角空白", "MarkdownEscaper 関連", "エスケープ済み文字列", "TABLE / KV", "なし", "中", "LLM 入力安全化", "基本設計", "高"],
    ]
    for row_index, row_values in enumerate(rows, start=5):
        _fill_row(worksheet, row_index, row_values)
    worksheet.auto_filter.ref = "A4:J11"
    _set_widths(worksheet, [10, 22, 28, 24, 16, 20, 10, 22, 16, 10])


def _build_parser_calc_sheet(
    workbook: Workbook,
    methods: Sequence[ParserMethodInfo],
    warnings: Sequence[WarningInfo],
) -> None:
    worksheet = workbook.create_sheet("設計計算_非表示")
    worksheet.sheet_state = "hidden"
    worksheet["A1"] = "Metric"
    worksheet["B1"] = "Value"
    worksheet["A2"] = "Method Count"
    worksheet["B2"] = len(methods)
    worksheet["A3"] = "Public Method Count"
    worksheet["B3"] = sum(
        1 for method in methods if not method.name.startswith("_") or method.name == "__init__"
    )
    worksheet["A4"] = "Private Helper Count"
    worksheet["B4"] = sum(
        1 for method in methods if method.name.startswith("_") and method.name != "__init__"
    )
    worksheet["A5"] = "Warning Type Count"
    worksheet["B5"] = len(warnings)
    worksheet["A6"] = "Default Density Threshold"
    worksheet["B6"] = 0.5


def _save_workbook_with_fallback(workbook: Workbook) -> Path:
    try:
        workbook.save(OUTPUT_PATH)
        return OUTPUT_PATH
    except PermissionError:
        fallback_path = OUTPUT_PATH.with_name("japanese_spec.generated.xlsx")
        workbook.save(fallback_path)
        return fallback_path


def create_japanese_spec() -> Path:
    methods = _load_parser_methods()
    warnings = _load_warning_definitions()
    workbook = Workbook()
    _build_overview_sheet(workbook)
    _build_database_sheet(workbook)
    _build_api_sheet(workbook)
    _build_screen_sheet(workbook)
    _build_parser_detail_sheet(workbook, methods)
    _build_method_matrix_sheet(workbook, methods)
    _build_sequence_sheet(workbook)
    _build_rule_sheet(workbook)
    _build_warning_sheet(workbook, warnings)
    _build_test_sheet(workbook)
    _build_hidden_sheet(workbook)
    _build_parser_calc_sheet(workbook, methods, warnings)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    saved_path = _save_workbook_with_fallback(workbook)
    workbook.close()

    print(f"Created: {saved_path}")
    print(f"Methods captured: {len(methods)}")
    print("Run parser with: uv run python script/create_test_excel.py")
    return saved_path


if __name__ == "__main__":
    create_japanese_spec()
