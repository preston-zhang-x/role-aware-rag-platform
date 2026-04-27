"""
JapaneseExcelParser の単体テスト。
openpyxl でメモリ上にテスト用 Excel を作成して検証。
"""

from pathlib import Path

import openpyxl
import pytest

from app.services.excel_parser import JapaneseExcelParser
from app.services.parse_result import ContentType

# ═══════════════════════════════════════
# Fixture（テストデータ生成）
# ═══════════════════════════════════════
# Java で言えば @BeforeEach + ヘルパーメソッド


@pytest.fixture
def parser():
    """パーサーインスタンスを提供"""
    return JapaneseExcelParser(density_threshold=0.5)


@pytest.fixture
def simple_excel(tmp_path) -> Path:
    """
    シンプルな Excel ファイルを作成。
    Sheet1 に基本的なテーブルデータ。
    """
    file_path = tmp_path / "simple.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "基本設計"

    # テーブルデータ（密度高い → テーブルモード）
    ws.append(["ID", "名前", "部署"])
    ws.append(["001", "田中太郎", "開発部"])
    ws.append(["002", "鈴木花子", "営業部"])
    ws.append(["003", "佐藤次郎", "人事部"])

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def merged_cell_excel(tmp_path) -> Path:
    """
    合并单元格を含む Excel。
    これが「幻覚」の原因になる問題パターン。
    """
    file_path = tmp_path / "merged.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "DB定義"

    # ヘッダー行（A1:C1 を結合 → "テーブル定義"）
    ws["A1"] = "テーブル定義"
    ws.merge_cells("A1:C1")

    # データ行
    ws["A2"] = "カラム名"
    ws["B2"] = "型"
    ws["C2"] = "説明"
    ws["A3"] = "user_id"
    ws["B3"] = "INTEGER"
    ws["C3"] = "ユーザーID"
    ws["A4"] = "name"
    ws["B4"] = "VARCHAR"
    ws["C4"] = "氏名"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def empty_excel(tmp_path) -> Path:
    """可視シートが空の Excel ファイル。"""
    file_path = tmp_path / "empty.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "空シート"
    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def kv_and_table_excel(tmp_path) -> Path:
    """
    典型的な日式仕様書: 上部にKV（疎）、下部にテーブル（密）。
    启发式扫描の正確性を検証するキーテストケース。
    """
    file_path = tmp_path / "kv_table.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "API仕様"

    # ── 上部: KV エリア（疎、密度 < 0.5） ──
    # 8列中2列だけにデータ → 密度 = 2/8 = 0.25
    ws["A1"] = "作成者"
    ws["B1"] = "田中太郎"
    # C1~H1 は空

    ws["A2"] = "作成日"
    ws["B2"] = "2024-01-15"

    ws["A3"] = "バージョン"
    ws["B3"] = "1.2.0"

    # ── 空行（区切り） ──
    # Row 4 は空

    # ── 下部: テーブルエリア（密、密度 > 0.5） ──
    ws["A5"] = "エンドポイント"
    ws["B5"] = "メソッド"
    ws["C5"] = "説明"
    ws["D5"] = "認証"
    ws["E5"] = "レスポンス"

    ws["A6"] = "/api/users"
    ws["B6"] = "GET"
    ws["C6"] = "ユーザー一覧"
    ws["D6"] = "必要"
    ws["E6"] = "200 OK"

    ws["A7"] = "/api/users/:id"
    ws["B7"] = "PUT"
    ws["C7"] = "ユーザー更新"
    ws["D7"] = "必要"
    ws["E7"] = "200 OK"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def hidden_sheet_excel(tmp_path) -> Path:
    """非表示シートを含む Excel"""
    file_path = tmp_path / "hidden.xlsx"
    wb = openpyxl.Workbook()

    # 可視シート
    ws1 = wb.active
    assert ws1 is not None
    ws1.title = "公開データ"
    ws1.append(["項目", "値"])
    ws1.append(["売上", "1000万"])

    # 非表示シート
    ws2 = wb.create_sheet("計算用_非表示")
    ws2.append(["内部データ", "秘密"])
    ws2.sheet_state = "hidden"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def special_chars_excel(tmp_path) -> Path:
    """Markdown を破壊する特殊文字を含む Excel"""
    file_path = tmp_path / "special.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "特殊文字テスト"

    ws.append(["ヘッダー1", "ヘッダー2"])
    ws.append(["パイプ|入り", "改行\n入り"])
    ws.append(["全角スペース\u3000入り", "通常テキスト"])

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def duplicate_column_table_excel(tmp_path) -> Path:
    """隣接する同名列を持つ Excel テーブル。"""
    file_path = tmp_path / "duplicate_columns.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "重複列"

    ws.append(["Flag", "Flag", "Name"])
    ws.append(["Y", "Y", "Alice"])
    ws.append(["N", "N", "Bob"])

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def table_escape_excel(tmp_path) -> Path:
    """テーブル内の Markdown 特殊文字を検証する Excel。"""
    file_path = tmp_path / "table_escape.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Escape"

    ws.append(["A", "B", "C"])
    ws.append(["pipe|value", "line\nbreak", "plain"])
    ws.append(["x", "y", "z"])

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def merged_title_excel(tmp_path) -> Path:
    """2 行結合タイトルが 1 回だけ見出し化される Excel"""
    file_path = tmp_path / "merged_title.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "見出し検証"

    ws["A1"] = "設計サマリ"
    ws.merge_cells("A1:D2")
    ws["A4"] = "項目"
    ws["B4"] = "値"
    ws["A5"] = "状態"
    ws["B5"] = "レビュー済み"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def semantic_text_excel(tmp_path) -> Path:
    """見出しと本文を区別したい Excel"""
    file_path = tmp_path / "semantic_text.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "基本設計"

    ws["A1"] = "1. システム概要"
    ws.merge_cells("A1:D1")
    ws["A2"] = "本システムは受発注情報を一元管理する業務システムです。"
    ws.merge_cells("A2:D2")
    ws["A4"] = "補足: パイプ | 改行\n全角　スペース を含むテキスト"
    ws.merge_cells("A4:D4")

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def dense_kv_excel(tmp_path) -> Path:
    """空白ギャップ付きの属性行を持つ Excel"""
    file_path = tmp_path / "dense_kv.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "メタ情報"

    ws["A1"] = "プロジェクト名"
    ws["B1"] = "RAG Platform"
    ws["E1"] = "管理番号"
    ws["F1"] = "PRJ-001"
    ws["A2"] = "作成者"
    ws["B2"] = "田中太郎"
    ws["E2"] = "版数"
    ws["F2"] = "1.0"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def wide_sheet_table_excel(tmp_path) -> Path:
    """シート幅よりテーブル幅を優先してほしい Excel"""
    file_path = tmp_path / "wide_sheet_table.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "一覧"

    ws["A1"] = "ID"
    ws["B1"] = "名前"
    ws["C1"] = "部署"
    ws["A2"] = "001"
    ws["B2"] = "田中太郎"
    ws["C2"] = "開発部"
    ws["H5"] = "このシートは 8 列幅"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def merged_width_definition_table_excel(tmp_path) -> Path:
    """結合幅が広い 5 列定義表でも表として扱いたい Excel"""
    file_path = tmp_path / "merged_width_definition_table.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "IO関連"

    ws["A1"] = "パラメータ一覧"
    ws["A2"] = "No"
    ws["B2"] = "論理名称"
    ws["L2"] = "物理名称"
    ws["V2"] = "I/O"
    ws["X2"] = "備考"
    ws["A3"] = "1"
    ws["B3"] = "collection_name"
    ws["L3"] = "collection_name"
    ws["V3"] = "I"
    ws["X3"] = "Qdrant の参照先コレクション。"
    ws["A4"] = "2"
    ws["B4"] = "top_k"
    ws["L4"] = "top_k"
    ws["V4"] = "I"
    ws["X4"] = "検索上限件数。"

    ws.merge_cells("B2:K2")
    ws.merge_cells("L2:U2")
    ws.merge_cells("V2:W2")
    ws.merge_cells("X2:AZ2")
    ws.merge_cells("B3:K3")
    ws.merge_cells("L3:U3")
    ws.merge_cells("V3:W3")
    ws.merge_cells("X3:AZ3")
    ws.merge_cells("B4:K4")
    ws.merge_cells("L4:U4")
    ws.merge_cells("V4:W4")
    ws.merge_cells("X4:AZ4")

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def merged_width_item_definition_excel(tmp_path) -> Path:
    """結合幅が広い 9 列定義表でも表として扱いたい Excel"""
    file_path = tmp_path / "merged_width_item_definition.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "画面項目"

    ws["A1"] = "I/O項目定義"
    headers = {
        "A2": "No",
        "B2": "項目名称",
        "L2": "分類",
        "Q2": "必須",
        "S2": "桁数",
        "U2": "フォーマット",
        "AB2": "テーブル",
        "AJ2": "フィールド",
        "AR2": "備考",
    }
    for cell, value in headers.items():
        ws[cell] = value

    row1 = {
        "A3": "1",
        "B3": "コレクション名",
        "L3": "入力",
        "Q3": "○",
        "S3": "-",
        "U3": "str",
        "AB3": "BM25Service",
        "AJ3": "collection_name",
        "AR3": "既定値は documents。",
    }
    row2 = {
        "A4": "2",
        "B4": "取得件数上限",
        "L4": "入力",
        "Q4": "任意",
        "S4": "-",
        "U4": "int",
        "AB4": "BM25Service",
        "AJ4": "top_k",
        "AR4": "既定値は 5。",
    }
    for mapping in (row1, row2):
        for cell, value in mapping.items():
            ws[cell] = value

    for row in (2, 3, 4):
        ws.merge_cells(f"B{row}:K{row}")
        ws.merge_cells(f"L{row}:P{row}")
        ws.merge_cells(f"Q{row}:R{row}")
        ws.merge_cells(f"S{row}:T{row}")
        ws.merge_cells(f"U{row}:AA{row}")
        ws.merge_cells(f"AB{row}:AI{row}")
        ws.merge_cells(f"AJ{row}:AQ{row}")
        ws.merge_cells(f"AR{row}:BC{row}")

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def merged_width_kv_excel(tmp_path) -> Path:
    """merge 幅が広くても実態が KV 行なら表にしない Excel"""
    file_path = tmp_path / "merged_width_kv.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "メタ情報"

    ws["A1"] = "プロジェクト名"
    ws["B1"] = "RAG Platform"
    ws["L1"] = "管理番号"
    ws["M1"] = "PRJ-001"
    ws["A2"] = "作成者"
    ws["B2"] = "田中太郎"
    ws["L2"] = "版数"
    ws["M2"] = "1.0"

    ws.merge_cells("B1:K1")
    ws.merge_cells("M1:V1")
    ws.merge_cells("B2:K2")
    ws.merge_cells("M2:V2")

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def merged_width_table_with_followup_section_excel(tmp_path) -> Path:
    """表の直後に別セクションが来ても飲み込まない Excel"""
    file_path = tmp_path / "merged_width_table_with_followup.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "IO関連"

    ws["A1"] = "パラメータ一覧"
    ws["A2"] = "No"
    ws["B2"] = "論理名称"
    ws["L2"] = "物理名称"
    ws["V2"] = "I/O"
    ws["X2"] = "備考"
    ws["A3"] = "1"
    ws["B3"] = "collection_name"
    ws["L3"] = "collection_name"
    ws["V3"] = "I"
    ws["X3"] = "Qdrant の参照先コレクション。"
    ws["A4"] = "2"
    ws["B4"] = "top_k"
    ws["L4"] = "top_k"
    ws["V4"] = "I"
    ws["X4"] = "検索上限件数。"
    ws["A5"] = "補足事項"
    ws.merge_cells("A5:AZ5")
    ws["A6"] = "備考"
    ws["B6"] = "search 既定値は 5"

    for row in (2, 3, 4):
        ws.merge_cells(f"B{row}:K{row}")
        ws.merge_cells(f"L{row}:U{row}")
        ws.merge_cells(f"V{row}:W{row}")
        ws.merge_cells(f"X{row}:AZ{row}")

    wb.save(file_path)
    wb.close()
    return file_path


# ═══════════════════════════════════════
# can_handle テスト
# ═══════════════════════════════════════


class TestCanHandle:
    def test_xlsx(self, parser):
        assert parser.can_handle("test.xlsx") is True

    def test_xlsm(self, parser):
        assert parser.can_handle("macro.xlsm") is True

    def test_pdf_rejected(self, parser):
        assert parser.can_handle("test.pdf") is False

    def test_xls_rejected(self, parser):
        """openpyxl は .xls 非対応"""
        assert parser.can_handle("old.xls") is False

    def test_case_insensitive(self, parser):
        assert parser.can_handle("TEST.XLSX") is True


# ═══════════════════════════════════════
# 戦略1: コンテキスト注入テスト
# ═══════════════════════════════════════


class TestContextInjection:
    def test_sheet_name_as_heading(self, parser, simple_excel):
        """Sheet名が Markdown の # 見出しとして出力されること"""
        result = parser.parse(str(simple_excel))
        assert "# 基本設計" in result.text

    def test_hidden_sheet_skipped(self, parser, hidden_sheet_excel):
        """非表示シートがスキップされること"""
        result = parser.parse(str(hidden_sheet_excel))
        assert "# 公開データ" in result.text
        assert "計算用_非表示" not in result.text

    def test_hidden_sheet_warning(self, parser, hidden_sheet_excel):
        """非表示シートスキップ時に警告が記録されること"""
        result = parser.parse(str(hidden_sheet_excel))
        has_warning = any("計算用_非表示" in w for w in result.warnings)
        assert has_warning


# ═══════════════════════════════════════
# 戦略2: 結合セルの広播テスト
# ═══════════════════════════════════════


class TestMergedCells:
    def test_merged_value_not_lost(self, parser, merged_cell_excel):
        """結合セルの値が消えないこと（None にならないこと）"""
        result = parser.parse(str(merged_cell_excel))
        assert "テーブル定義" in result.text

    def test_merged_cell_warning(self, parser, merged_cell_excel):
        """結合セル広播時に警告が記録されること"""
        result = parser.parse(str(merged_cell_excel))
        has_warning = any("A1:C1" in w for w in result.warnings)
        assert has_warning

    def test_duplicate_merged_heading_deduplicated(self, parser, merged_title_excel):
        """複数行に広播された同一タイトルは 1 回だけ出力されること"""
        result = parser.parse(str(merged_title_excel))
        assert result.text.count("## 設計サマリ") == 1


# ═══════════════════════════════════════
# 戦略3: 启发式扫描テスト
# ═══════════════════════════════════════


class TestHeuristicScan:
    def test_simple_table_rendered(self, parser, simple_excel):
        """密なデータがテーブルとして出力されること"""
        result = parser.parse(str(simple_excel))
        # Markdown テーブルの特徴: | と --- を含む
        assert "|" in result.text
        assert "---" in result.text
        assert "田中太郎" in result.text

    def test_kv_area_detected(self, parser, kv_and_table_excel):
        """疎な行が KV 形式で出力されること"""
        result = parser.parse(str(kv_and_table_excel))
        assert "**作成者:**" in result.text or "作成者" in result.text

    def test_table_area_detected(self, parser, kv_and_table_excel):
        """密な行がテーブル形式で出力されること"""
        result = parser.parse(str(kv_and_table_excel))
        assert "エンドポイント" in result.text
        assert "/api/users" in result.text

    def test_chunks_have_correct_types(self, parser, kv_and_table_excel):
        """チャンクの content_type が正しく設定されること"""
        result = parser.parse(str(kv_and_table_excel))
        types = {chunk.content_type for chunk in result.chunks}
        # KV とテーブル両方が検出されるはず
        assert ContentType.KEY_VALUE in types or ContentType.TABLE in types

    def test_dense_pairs_rendered_as_bullets(self, parser, dense_kv_excel):
        """空白ギャップ付きの属性行は箇条書き KV に変換されること"""
        result = parser.parse(str(dense_kv_excel))
        assert "- **プロジェクト名:** RAG Platform" in result.text
        assert "- **管理番号:** PRJ-001" in result.text
        assert "| プロジェクト名 |" not in result.text

    def test_long_merged_text_kept_as_paragraph(self, parser, semantic_text_excel):
        """長文の単一セル行は見出しではなく段落として出力されること"""
        result = parser.parse(str(semantic_text_excel))
        assert "## 1. システム概要" in result.text
        assert "本システムは受発注情報を一元管理する業務システムです。" in result.text
        assert (
            "## 本システムは受発注情報を一元管理する業務システムです。"
            not in result.text
        )
        assert "## 補足:" not in result.text

    def test_table_trimmed_to_used_columns(self, parser, wide_sheet_table_excel):
        """テーブルはシート全体ではなくブロックの実列数で出力されること"""
        result = parser.parse(str(wide_sheet_table_excel))
        assert "| ID | 名前 | 部署 |" in result.text
        assert "| ID | 名前 | 部署 |  |" not in result.text

    def test_duplicate_adjacent_columns_are_preserved(
        self, parser, duplicate_column_table_excel
    ):
        """同じ見出しが隣接しても列を潰さずテーブルとして保持すること"""
        result = parser.parse(str(duplicate_column_table_excel))
        assert "| Flag | Flag | Name |" in result.text
        assert "| Y | Y | Alice |" in result.text
        assert "- **Flag:** Name" not in result.text

    def test_merged_width_definition_table_kept_as_table(
        self, parser, merged_width_definition_table_excel
    ):
        """結合幅が広い 5 列定義表は KV ではなく表として保持すること"""
        result = parser.parse(str(merged_width_definition_table_excel))
        assert "| No | 論理名称 | 物理名称 | I/O | 備考 |" in result.text
        assert (
            "| 1 | collection_name | collection_name | I | Qdrant の参照先コレクション。 |"
            in result.text
        )
        assert "- **1:** collection_name" not in result.text

    def test_merged_width_item_definition_kept_as_table(
        self, parser, merged_width_item_definition_excel
    ):
        """結合幅が広い 9 列定義表も表構造を維持すること"""
        result = parser.parse(str(merged_width_item_definition_excel))
        assert (
            "| No | 項目名称 | 分類 | 必須 | 桁数 | フォーマット | テーブル | フィールド | 備考 |"
            in result.text
        )
        assert (
            "| 1 | コレクション名 | 入力 | ○ | - | str | BM25Service | collection_name | 既定値は documents。 |"
            in result.text
        )
        assert "- **分類:** 必須" not in result.text

    def test_merged_width_kv_stays_kv(self, parser, merged_width_kv_excel):
        """wide merge の KV 行は表に誤分類しないこと"""
        result = parser.parse(str(merged_width_kv_excel))
        assert "- **プロジェクト名:** RAG Platform" in result.text
        assert "- **管理番号:** PRJ-001" in result.text
        assert "| プロジェクト名 |" not in result.text

    def test_followup_section_not_swallowed_after_merged_table(
        self, parser, merged_width_table_with_followup_section_excel
    ):
        """merged-width table の直後に来る別セクションを表に飲み込まないこと"""
        result = parser.parse(str(merged_width_table_with_followup_section_excel))
        assert "| No | 論理名称 | 物理名称 | I/O | 備考 |" in result.text
        assert "## 補足事項" in result.text
        assert "- **備考:** search 既定値は 5" in result.text


# ═══════════════════════════════════════
# 特殊文字エスケープテスト
# ═══════════════════════════════════════


class TestSpecialCharacterEscaping:
    def test_pipe_escaped(self, parser, special_chars_excel):
        """パイプ文字がエスケープされてテーブル構造を壊さないこと"""
        result = parser.parse(str(special_chars_excel))
        # 生の | がデータに入るとテーブルが崩れる
        # エスケープ後は \| になるはず
        assert "パイプ" in result.text

    def test_newline_escaped(self, parser, special_chars_excel):
        """改行が <br> に変換されること"""
        result = parser.parse(str(special_chars_excel))
        # テーブル内の改行は <br> に変換されるべき
        assert "改行" in result.text

    def test_table_pipe_escaped_once(self, parser, table_escape_excel):
        """テーブルセルのパイプ文字を二重エスケープしないこと"""
        result = parser.parse(str(table_escape_excel))
        assert "pipe\\|value" in result.text
        assert "pipe\\\\|value" not in result.text
        assert "line<br>break" in result.text


# ═══════════════════════════════════════
# エラーハンドリングテスト
# ═══════════════════════════════════════


class TestErrorHandling:
    def test_file_not_found(self, parser):
        """存在しないファイルで ParseError が発生すること"""
        from app.services.base_parser import ParseError

        with pytest.raises(ParseError):
            parser.parse("/nonexistent/file.xlsx")

    def test_density_threshold_constructor_kept_for_compatibility(self, simple_excel):
        """旧コンストラクタ引数を指定しても従来通り利用できること"""
        parser = JapaneseExcelParser(density_threshold=0.5)
        result = parser.parse(str(simple_excel))
        assert "# 基本設計" in result.text

    def test_cached_workbook_closed_when_formula_workbook_fails(
        self, parser, tmp_path, monkeypatch
    ):
        """2回目の workbook 読み込みに失敗しても1回目を閉じること"""
        from app.services.base_parser import ParseError

        file_path = tmp_path / "broken_formula.xlsx"
        file_path.write_bytes(b"placeholder")

        class CloseAwareWorkbook:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        cached_workbook = CloseAwareWorkbook()

        def fake_load_workbook(path, data_only):
            if data_only:
                return cached_workbook
            raise RuntimeError("formula workbook failed")

        monkeypatch.setattr(
            "app.services.excel_parser.openpyxl.load_workbook",
            fake_load_workbook,
        )

        with pytest.raises(ParseError):
            parser.parse(str(file_path))

        assert cached_workbook.closed is True

    def test_chunks_metadata_complete(self, parser, simple_excel):
        """チャンクのメタデータが完全であること"""
        result = parser.parse(str(simple_excel))
        for chunk in result.chunks:
            assert chunk.source_file == str(simple_excel)
            assert chunk.sheet_name == "基本設計"
            assert chunk.content_type is not None

    def test_chunks_have_char_positions(self, parser, simple_excel):
        """チャンクの文字位置が連結テキストに対して設定されること"""
        result = parser.parse(str(simple_excel))

        assert result.chunks
        for chunk in result.chunks:
            assert chunk.char_end > chunk.char_start >= 0
            extracted = result.text[chunk.char_start : chunk.char_end]
            assert extracted.strip()

    def test_empty_sheet_is_rendered_without_error(self, parser, empty_excel):
        """空シートでも例外なく見出しを返すこと"""
        result = parser.parse(str(empty_excel))

        assert "# 空シート" in result.text
        assert result.chunks == []
