"""
PDFMarkdownParser の単体テスト。
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.base_parser import ParseError
from app.services.parse_result import ContentType
from app.services.pdf_parser import PDFMarkdownParser


@pytest.fixture
def parser():
    return PDFMarkdownParser()


# ═══════════════════════════════════════
# can_handle テスト
# ═══════════════════════════════════════


class TestCanHandle:
    def test_pdf(self, parser):
        assert parser.can_handle("document.pdf") is True

    def test_xlsx_rejected(self, parser):
        assert parser.can_handle("test.xlsx") is False

    def test_case_insensitive(self, parser):
        assert parser.can_handle("DOC.PDF") is True


# ═══════════════════════════════════════
# エラーハンドリングテスト
# ═══════════════════════════════════════


class TestErrorHandling:
    def test_file_not_found(self, parser):
        with pytest.raises(ParseError):
            parser.parse("/nonexistent/file.pdf")


# ═══════════════════════════════════════
# Mock を使った解析テスト
# Java の Mockito に相当
# ═══════════════════════════════════════


class TestPDFParsing:
    def test_text_extraction(self, parser, tmp_path):
        """
        pdfplumber をモックして、テキスト抽出をテスト。

        Java で言えば:
        @Mock PDFTextStripper stripper;
        when(stripper.getText(any())).thenReturn("Hello PDF");
        """
        # ── モックページを作成 ──
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "これはテスト文書です。"
        mock_page.extract_tables.return_value = []
        mock_page.images = []

        # ── pdfplumber.open をモック ──
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        # 実際のファイルパスが必要（存在チェックのため）
        dummy_file = tmp_path / "test.pdf"
        dummy_file.write_bytes(b"dummy")

        with patch("app.services.pdf_parser.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf

            result = parser.parse(str(dummy_file))

        assert "これはテスト文書です" in result.text
        assert "## Page 1" in result.text

    def test_table_extraction(self, parser, tmp_path):
        """テーブル抽出のテスト"""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "テーブルあり"
        mock_page.extract_tables.return_value = [
            [["名前", "年齢"], ["太郎", "30"], ["花子", "25"]]
        ]
        mock_page.images = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        dummy_file = tmp_path / "test.pdf"
        dummy_file.write_bytes(b"dummy")

        with patch("app.services.pdf_parser.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf

            result = parser.parse(str(dummy_file))

        assert "名前" in result.text
        assert "太郎" in result.text
        # テーブルチャンクが存在すること
        table_chunks = [c for c in result.chunks if c.content_type == ContentType.TABLE]
        assert len(table_chunks) >= 1

    def test_scan_page_detection(self, parser, tmp_path):
        """スキャンページが検出されること"""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""  # テキストほぼなし
        mock_page.extract_tables.return_value = []
        mock_page.images = [{"x0": 0, "y0": 0}]  # 画像あり

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        dummy_file = tmp_path / "scan.pdf"
        dummy_file.write_bytes(b"dummy")

        with patch("app.services.pdf_parser.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf

            result = parser.parse(str(dummy_file))

        assert len(result.warnings) > 0
        has_scan_warning = any("スキャン" in w for w in result.warnings)
        assert has_scan_warning

    def test_page_number_in_chunks(self, parser, tmp_path):
        """チャンクに page_number が設定されること"""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content"
        mock_page.extract_tables.return_value = []
        mock_page.images = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        dummy_file = tmp_path / "test.pdf"
        dummy_file.write_bytes(b"dummy")

        with patch("app.services.pdf_parser.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf

            result = parser.parse(str(dummy_file))

        assert result.chunks[0].page_number == 1
