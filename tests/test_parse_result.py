from app.services.parse_result import (
    ChunkMeta,
    ContentType,
    MarkdownEscaper,
    ParseResult,
    ParserWarning,
)

# ═══════════════════════════════════════
# ContentType Enum テスト
# ═══════════════════════════════════════


class TestContentType:
    """Java で言えば: class ContentTypeTest"""

    def test_enum_values(self):
        """全ての enum 値が正しく定義されていること"""
        assert ContentType.TABLE.value == "table"
        assert ContentType.KEY_VALUE.value == "key_value"
        assert ContentType.TEXT.value == "text"
        assert ContentType.SHAPE.value == "shape"

    def test_enum_count(self):
        """enum の数が期待値と一致すること"""
        assert len(ContentType) == 4


# ═══════════════════════════════════════
# ParserWarning Enum テスト
# ═══════════════════════════════════════


class TestParserWarning:
    def test_all_warnings_defined(self):
        """6 種類の警告が全て定義されていること"""
        assert len(ParserWarning) == 6

    def test_warning_values_are_non_empty(self):
        """全ての警告メッセージが空文字でないこと"""
        for warning in ParserWarning:
            assert len(warning.value) > 0, f"{warning.name} の値が空です"


# ═══════════════════════════════════════
# ChunkMeta テスト
# ═══════════════════════════════════════


class TestChunkMeta:
    def test_required_fields(self):
        """必須フィールドのみで生成できること"""
        chunk = ChunkMeta(
            source_file="test.xlsx",
            content_type=ContentType.TABLE,
        )
        assert chunk.source_file == "test.xlsx"
        assert chunk.content_type == ContentType.TABLE

    def test_optional_fields_default_to_none(self):
        """オプションフィールドのデフォルト値が正しいこと"""
        chunk = ChunkMeta(
            source_file="test.xlsx",
            content_type=ContentType.TABLE,
        )
        assert chunk.sheet_name is None
        assert chunk.page_number is None
        assert chunk.cell_range is None
        assert chunk.merged_ranges == []
        assert chunk.is_broadcast_fill is False

    def test_all_fields(self):
        """全フィールドを指定して生成できること"""
        chunk = ChunkMeta(
            source_file="test.xlsx",
            content_type=ContentType.TABLE,
            sheet_name="DB定義",
            page_number=None,
            cell_range="A1:F20",
            merged_ranges=["B2:D4"],
            is_broadcast_fill=True,
        )
        assert chunk.sheet_name == "DB定義"
        assert chunk.cell_range == "A1:F20"
        assert chunk.merged_ranges == ["B2:D4"]
        assert chunk.is_broadcast_fill is True

    def test_merged_ranges_not_shared_between_instances(self):
        """
        ⚠️ 最重要テスト: default_factory で各インスタンスが独立リストを持つこと。
        Java で言えば: static List を共有してないかの確認。
        """
        chunk1 = ChunkMeta(source_file="a.xlsx", content_type=ContentType.TABLE)
        chunk2 = ChunkMeta(source_file="b.xlsx", content_type=ContentType.TABLE)
        chunk1.merged_ranges.append("A1:B2")
        assert chunk2.merged_ranges == []  # chunk2 は影響を受けないこと！


# ═══════════════════════════════════════
# ParseResult テスト
# ═══════════════════════════════════════


class TestParseResult:
    def test_minimal_creation(self):
        """最小構成で生成できること"""
        result = ParseResult(text="# Test")
        assert result.text == "# Test"
        assert result.chunks == []
        assert result.warnings == []

    def test_full_creation(self):
        """全フィールドを指定して生成できること"""
        chunk = ChunkMeta(source_file="test.xlsx", content_type=ContentType.TEXT)
        result = ParseResult(
            text="# Hello",
            chunks=[chunk],
            warnings=["some warning"],
        )
        assert len(result.chunks) == 1
        assert len(result.warnings) == 1


# ═══════════════════════════════════════
# MarkdownEscaper テスト
# ═══════════════════════════════════════


class TestMarkdownEscaper:
    # ── escape_cell テスト ──

    def test_escape_pipe(self):
        """パイプ文字がエスケープされること"""
        assert MarkdownEscaper.escape_cell("A|B") == "A\\|B"

    def test_escape_newline(self):
        """改行が <br> に変換されること"""
        assert MarkdownEscaper.escape_cell("line1\nline2") == "line1<br>line2"

    def test_escape_carriage_return(self):
        """CR が除去されること"""
        assert MarkdownEscaper.escape_cell("hello\r\nworld") == "hello<br>world"

    def test_escape_fullwidth_space(self):
        """全角スペースが半角に変換されること"""
        assert MarkdownEscaper.escape_cell("hello\u3000world") == "hello world"

    def test_escape_none(self):
        """None が空文字になること"""
        assert MarkdownEscaper.escape_cell(None) == ""

    def test_escape_strips_whitespace(self):
        """前後の空白が除去されること"""
        assert MarkdownEscaper.escape_cell("  hello  ") == "hello"

    def test_escape_numeric_value(self):
        """数値が文字列に変換されること"""
        assert MarkdownEscaper.escape_cell(42) == "42"

    # ── make_table テスト ──

    def test_make_table_basic(self):
        """基本的なテーブルが正しく生成されること"""
        headers = ["Name", "Age"]
        rows = [["Alice", "30"], ["Bob", "25"]]
        result = MarkdownEscaper.make_table(headers, rows)

        lines = result.split("\n")
        assert lines[0] == "| Name | Age |"
        assert lines[1] == "| --- | --- |"
        assert lines[2] == "| Alice | 30 |"
        assert lines[3] == "| Bob | 25 |"

    def test_make_table_empty_headers(self):
        """ヘッダーが空の場合は空文字を返すこと"""
        assert MarkdownEscaper.make_table([], []) == ""

    def test_make_table_escapes_pipe_in_data(self):
        """データ内のパイプ文字がエスケープされること"""
        result = MarkdownEscaper.make_table(["Col"], [["A|B"]])
        assert "A\\|B" in result

    def test_make_table_pads_short_rows(self):
        """列数不足の行が空文字で埋められること"""
        headers = ["A", "B", "C"]
        rows = [["x"]]  # 1列しかない
        result = MarkdownEscaper.make_table(headers, rows)
        assert result.count("|") >= 4  # 3列 + 両端
