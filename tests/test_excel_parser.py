"""
JapaneseExcelParser の単体テスト。
openpyxl でメモリ上にテスト用 Excel を作成して検証。
"""

from pathlib import Path

import openpyxl
import pytest

from app.services.excel_parser import JapaneseExcelParser
from app.services.parse_result import BlockKind, ContentType

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
def structured_id_lists_excel(tmp_path) -> Path:
    """会社固有でない ID 一覧シートを持つ Excel"""
    file_path = tmp_path / "structured_id_lists.xlsx"
    wb = openpyxl.Workbook()

    ws1 = wb.active
    assert ws1 is not None
    ws1.title = "要求一覧"
    ws1["A1"] = "要求一覧"
    ws1["A3"] = "一覧の説明"
    ws1.append([])
    ws1.append(["REQ-ID", "要求名", "カテゴリ", "備考"])
    ws1.append(["REQ-010", "Excel 仕様書解析", "Parser", "Hidden sheet は warning"])
    ws1.append(["REQ-011", "PDF 解析", "Parser", "スキャンページは warning"])

    ws2 = wb.create_sheet("画面一覧")
    ws2["A1"] = "画面一覧"
    ws2["A3"] = "推定 UI 一覧"
    ws2.append([])
    ws2.append(["PAGE-ID", "画面名", "概要"])
    ws2.append(["PAGE-004", "ヘルス監視画面", "運用 UI"])
    ws2.append(["PAGE-003", "RAG 問合せ画面", "検索 UI"])

    ws3 = wb.create_sheet("設定一覧")
    ws3["A1"] = "設定一覧"
    ws3["A3"] = "設定の説明"
    ws3.append([])
    ws3.append(["CONF-ID", "クラス", "項目", "コード既定値"])
    ws3.append(["CONF-002", "SecuritySettings", "algorithm", "HS256"])
    ws3.append(["CONF-003", "SecuritySettings", "access_token_expire_minutes", "30"])

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def record_detail_excel(tmp_path) -> Path:
    """固定 section 名に依存しない詳細仕様ブロック"""
    file_path = tmp_path / "record_detail.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "API仕様"

    ws["A1"] = "API仕様"
    ws["A3"] = "詳細説明"

    ws["A5"] = "API-004 文書一覧取得"
    ws.merge_cells("A5:G5")
    ws.append([])
    ws["A6"] = "Method"
    ws["B6"] = "GET"
    ws["C6"] = "Path"
    ws["D6"] = "/api/v1/docs/"
    ws["E6"] = "認可"
    ws["F6"] = "Bearer 必須 / 認証済み"

    ws["A8"] = "Parameters"
    ws.merge_cells("A8:G8")
    ws.append([])
    ws["A9"] = "項目名"
    ws["B9"] = "型"
    ws["C9"] = "必須"
    ws["D9"] = "既定値"
    ws["E9"] = "ルール"
    ws["F9"] = "位置"
    ws["A10"] = "skip"
    ws["B10"] = "int"
    ws["C10"] = "N"
    ws["D10"] = "0"
    ws["E10"] = "ge=0"
    ws["F10"] = "query"
    ws["A11"] = "limit"
    ws["B11"] = "int"
    ws["C11"] = "N"
    ws["D11"] = "10"
    ws["E11"] = "ge=1, le=100"
    ws["F11"] = "query"

    ws["A13"] = "API-005 文書詳細取得"
    ws.merge_cells("A13:G13")
    ws["A14"] = "Method"
    ws["B14"] = "GET"
    ws["C14"] = "Path"
    ws["D14"] = "/api/v1/docs/{doc_id}"
    ws["E14"] = "認可"
    ws["F14"] = "Bearer 必須 / 認証済み"
    ws["A16"] = "Path Parameters"
    ws.merge_cells("A16:G16")
    ws["A17"] = "項目名"
    ws["B17"] = "型"
    ws["C17"] = "必須"
    ws["D17"] = "ルール"
    ws["E17"] = "位置"
    ws["A18"] = "doc_id"
    ws["B18"] = "int"
    ws["C18"] = "Y"
    ws["D18"] = "Path パラメータ"
    ws["E18"] = "path"

    ws["A20"] = "API-010 Ready チェック"
    ws.merge_cells("A20:G20")
    ws["A21"] = "Method"
    ws["B21"] = "GET"
    ws["C21"] = "Path"
    ws["D21"] = "/api/v1/health/ready"
    ws["A23"] = "Failure Cases"
    ws.merge_cells("A23:G23")
    ws["A24"] = "Status"
    ws["B24"] = "detail"
    ws["C24"] = "備考"
    ws["A25"] = "503 Service Unavailable"
    ws["B25"] = '{"status":"degraded","checks":...}'
    ws["C25"] = "-"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def parent_child_excel(tmp_path) -> Path:
    """親子構造を持つ汎用テーブル定義 Excel"""
    file_path = tmp_path / "parent_child.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "テーブル定義"

    ws["A1"] = "テーブル定義"
    ws["A3"] = "現行 SQLAlchemy モデルの列定義。"
    ws["A5"] = "TABLE-002 documents"
    ws.merge_cells("A5:L5")
    ws["A6"] = "概要"
    ws["B6"] = "文書 CRUD の永続化テーブル。"
    ws["C6"] = "ソース"
    ws["D6"] = "app\\db\\models\\document.py"
    ws["A7"] = "FIELD-ID"
    ws["B7"] = "カラム名"
    ws["C7"] = "型"
    ws["D7"] = "Python型"
    ws["E7"] = "長さ"
    ws["F7"] = "PK"
    ws["G7"] = "UK"
    ws["H7"] = "NULL"
    ws["I7"] = "既定値"
    ws["J7"] = "自動/更新"
    ws["K7"] = "説明"
    ws["L7"] = "備考"
    ws["A8"] = "FIELD-TABLE-002-005"
    ws["B8"] = "updated_at"
    ws["C8"] = "TIMESTAMP"
    ws["D8"] = "datetime"
    ws["F8"] = "N"
    ws["G8"] = "N"
    ws["H8"] = "N"
    ws["I8"] = "func.now()"
    ws["J8"] = "server_default, onupdate"
    ws["K8"] = "更新日時"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture
def fallback_placeholder_excel(tmp_path) -> Path:
    """占位行が見出し化されない fallback 用 Excel"""
    file_path = tmp_path / "fallback_placeholder.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Fallback"

    ws["A1"] = "Fallback"
    ws["A3"] = "Header"
    ws["A4"] = "項目名"
    ws["B4"] = "型"
    ws["A5"] = "-"
    ws["B5"] = "-"

    wb.save(file_path)
    wb.close()
    return file_path


@pytest.fixture(scope="module")
def spec_parse_result() -> tuple[JapaneseExcelParser, object]:
    parser = JapaneseExcelParser(density_threshold=0.5)
    spec_path = Path("docs") / "role_aware_rag_platform_spec.xlsx"
    result = parser.parse(str(spec_path))
    return parser, result


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
        assert "## 本システムは受発注情報を一元管理する業務システムです。" not in result.text
        assert "## 補足:" not in result.text

    def test_table_trimmed_to_used_columns(self, parser, wide_sheet_table_excel):
        """テーブルはシート全体ではなくブロックの実列数で出力されること"""
        result = parser.parse(str(wide_sheet_table_excel))
        assert "| ID | 名前 | 部署 |" in result.text
        assert "| ID | 名前 | 部署 |  |" not in result.text


class TestStructuredBlocks:
    def _find_block(
        self,
        result,
        *,
        record_id: str | None = None,
        sheet_name: str | None = None,
        section_name: str | None = None,
    ):
        for block in result.blocks:
            if record_id is not None and block.meta.record_id != record_id:
                continue
            if sheet_name is not None and block.meta.sheet_name != sheet_name:
                continue
            if section_name is not None and block.meta.section_name != section_name:
                continue
            return block
        return None

    def test_id_list_generates_record_summary_blocks(
        self, parser, structured_id_lists_excel
    ):
        result = parser.parse(str(structured_id_lists_excel))

        req_block = self._find_block(result, record_id="REQ-010")
        assert req_block is not None
        assert req_block.meta.block_kind == BlockKind.RECORD_SUMMARY
        assert "カテゴリ: Parser" in req_block.text

        page_block = self._find_block(result, record_id="PAGE-004")
        assert page_block is not None
        assert "ヘルス監視画面" in page_block.text

        conf_block = self._find_block(result, record_id="CONF-002")
        assert conf_block is not None
        assert "コード既定値: HS256" in conf_block.text

    def test_record_detail_generates_section_blocks(
        self, parser, record_detail_excel
    ):
        result = parser.parse(str(record_detail_excel))

        query_block = self._find_block(
            result, record_id="API-004", section_name="Parameters"
        )
        assert query_block is not None
        assert query_block.meta.block_kind == BlockKind.RECORD_SECTION
        assert "limit | 型=int | 必須=N | 既定値=10 | ルール=ge=1, le=100" in query_block.text

        path_block = self._find_block(
            result,
            record_id="API-005",
            section_name="Path Parameters",
        )
        assert path_block is not None
        assert "項目名: doc_id" in path_block.text

        error_block = self._find_block(
            result,
            record_id="API-010",
            section_name="Failure Cases",
        )
        assert error_block is not None
        assert "503 Service Unavailable" in error_block.text

    def test_parent_child_generates_parent_and_child_blocks(
        self, parser, parent_child_excel
    ):
        result = parser.parse(str(parent_child_excel))

        parent_block = self._find_block(result, record_id="TABLE-002")
        assert parent_block is not None
        assert parent_block.meta.block_kind == BlockKind.RECORD_SUMMARY
        assert "文書 CRUD の永続化テーブル" in parent_block.text

        child_block = self._find_block(result, record_id="FIELD-TABLE-002-005")
        assert child_block is not None
        assert child_block.meta.block_kind == BlockKind.RECORD_ROW
        assert child_block.meta.parent_record_id == "TABLE-002"
        assert "server_default, onupdate" in child_block.text

    def test_fallback_skips_placeholder_heading(self, parser, fallback_placeholder_excel):
        result = parser.parse(str(fallback_placeholder_excel))
        assert "## -" not in result.text
        assert "| 項目名 | 型 |" not in result.text


class TestRealSpecStructuredBlocks:
    @pytest.mark.parametrize(
        ("record_id", "section_name", "expected"),
        [
            ("FN-007", None, "文書削除"),
            ("FN-010", None, "カテゴリ: Parser"),
            ("SCR-004", None, "ヘルス監視画面"),
            ("ITM-SCR003-002", None, "初期値: viewer"),
            ("IF-007", None, "Method: DELETE"),
            ("IF-005", "Path", "doc_id"),
            ("IF-010", "Error", "503 Service Unavailable"),
            ("CFG-002", None, "コード既定値: HS256"),
            ("RL-012", None, "FORMULA_NO_CACHE"),
            ("COL-TBL-002-005", None, "server_default, onupdate"),
        ],
    )
    def test_expected_answers_live_in_single_block(
        self,
        spec_parse_result,
        record_id: str,
        section_name: str | None,
        expected: str,
    ):
        _, result = spec_parse_result
        matched_blocks = [
            block
            for block in result.blocks
            if block.meta.record_id == record_id
            and (section_name is None or block.meta.section_name == section_name)
        ]

        assert matched_blocks, f"{record_id=} {section_name=} に対応する block がありません"
        assert any(expected in block.text for block in matched_blocks)


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


# ═══════════════════════════════════════
# エラーハンドリングテスト
# ═══════════════════════════════════════


class TestErrorHandling:
    def test_file_not_found(self, parser):
        """存在しないファイルで ParseError が発生すること"""
        from app.services.base_parser import ParseError

        with pytest.raises(ParseError):
            parser.parse("/nonexistent/file.xlsx")

    def test_chunks_metadata_complete(self, parser, simple_excel):
        """チャンクのメタデータが完全であること"""
        result = parser.parse(str(simple_excel))
        for chunk in result.chunks:
            assert chunk.source_file == str(simple_excel)
            assert chunk.sheet_name == "基本設計"
            assert chunk.content_type is not None
