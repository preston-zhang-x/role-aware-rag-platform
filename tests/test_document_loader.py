"""
DocumentLoader の単体テスト。
レジストリとフォールバックチェーンの動作を検証。
"""

import pytest

from app.services.base_parser import BaseParser, ParseError
from app.services.document_loader import DocumentLoader
from app.services.parse_result import ParseResult


@pytest.fixture
def loader():
    return DocumentLoader()


# ═══════════════════════════════════════
# レジストリテスト
# ═══════════════════════════════════════


class TestRegistry:
    def test_supported_extensions(self, loader):
        """デフォルトでサポートされる拡張子"""
        exts = loader.get_supported_extensions()
        assert ".xlsx" in exts
        assert ".pdf" in exts
        assert ".xls" in exts
        assert ".html" in exts
        assert ".htm" in exts

    def test_register_new_extension(self, loader):
        """新しい拡張子を登録できること"""

        class DummyParser(BaseParser):
            def parse(self, file_path: str) -> ParseResult:
                return ParseResult(text="dummy")

            def can_handle(self, file_path: str) -> bool:
                return True

        loader.register(".docx", [DummyParser])
        assert ".docx" in loader.get_supported_extensions()

    def test_unsupported_extension(self, loader, tmp_path):
        """未対応拡張子で ParseError が発生すること"""
        dummy_file = tmp_path / "test.unknown"
        dummy_file.write_text("test")

        with pytest.raises(ParseError) as exc_info:
            loader.load(str(dummy_file))
        assert "サポートされていない" in str(exc_info.value)


# ═══════════════════════════════════════
# フォールバックチェーンテスト
# ═══════════════════════════════════════


class TestFallbackChain:
    def test_primary_success(self, loader, tmp_path):
        """
        Primary パーサーが成功 → フォールバック不要。
        Java で言えば:
            verify(fallbackParser, never()).parse(any());
        """
        excel_file = tmp_path / "test.xlsx"
        # openpyxl で有効な Excel を作成
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["テスト", "データ"])
        wb.save(excel_file)
        wb.close()

        result = loader.load(str(excel_file))
        assert result.text is not None
        # フォールバック警告がないこと
        fallback_warnings = [w for w in result.warnings if "フォールバック" in w]
        assert len(fallback_warnings) == 0

    def test_file_not_found(self, loader):
        """存在しないファイルで ParseError"""
        with pytest.raises(ParseError):
            loader.load("/nonexistent/file.xlsx")

    def test_all_parsers_fail(self, loader, tmp_path):
        """全パーサー失敗時のエラーメッセージ"""

        class FailParser(BaseParser):
            def parse(self, file_path: str) -> ParseResult:
                raise ParseError("意図的に失敗")

            def can_handle(self, file_path: str) -> bool:
                return True

        loader.register(".fail", [FailParser])

        dummy_file = tmp_path / "test.fail"
        dummy_file.write_text("test")

        with pytest.raises(ParseError) as exc_info:
            loader.load(str(dummy_file))
        assert "全てのパーサーが失敗" in str(exc_info.value)


# ═══════════════════════════════════════
# 統合的な動作テスト
# ═══════════════════════════════════════


class TestIntegration:
    def test_excel_end_to_end(self, loader, tmp_path):
        """Excel ファイルの E2E テスト"""
        import openpyxl

        file_path = tmp_path / "e2e.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "テストシート"
        ws.append(["ID", "名前"])
        ws.append(["1", "テスト太郎"])
        wb.save(file_path)
        wb.close()

        result = loader.load(str(file_path))

        # 基本チェック
        assert result.text is not None
        assert len(result.text) > 0
        assert "テストシート" in result.text
        assert "テスト太郎" in result.text

        # メタデータチェック
        assert len(result.chunks) > 0
        assert result.chunks[0].source_file == str(file_path)

    def test_html_uses_markitdown_fallback(self, loader, tmp_path):
        file_path = tmp_path / "page.html"
        file_path.write_text(
            "<!DOCTYPE html><html><body><article><h1>Title</h1><p>Alpha beta</p></article></body></html>",
            encoding="utf-8",
        )

        result = loader.load(str(file_path))

        assert "Title" in result.text
        assert "Alpha beta" in result.text
        assert any("フォールバック" in warning for warning in result.warnings)
