import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI
from qdrant_client.grpc import points_pb2
from qdrant_client.http import models
from qdrant_client.http.models import PointStruct

from app.clients.qdrant_client import get_qdrant_client
from app.core.config import openai_settings
from app.services.document_loader import DocumentLoader

DEFAULT_COLLECTION = "documents"  # Qdrant コレクション名
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
BATCH_SIZE = 64

# 正規表現: Excel 関数の検出パターン
_FORMULA_PATTERN = re.compile(
    r"\b(SUM|AVERAGE|COUNT|COUNTA|COUNTIF|COUNTIFS"
    r"|VLOOKUP|HLOOKUP|XLOOKUP|INDEX|MATCH"
    r"|IF|IFS|SUMIF|SUMIFS|SUMPRODUCT"
    r"|MAX|MIN|LEFT|RIGHT|MID|LEN|TRIM|CONCATENATE"
    r"|ROUND|ROUNDUP|ROUNDDOWN)\s*\(",
    re.IGNORECASE,
)

_HEADING_PATTERN = re.compile(r"^(#{1,2})\s+.+$")  # Markdown 見出しの検出
_SENTENCE_BOUNDARY_PATTERN = re.compile(
    r"(?<=[。！？.!?…])(?![」』）])\s*"
)  # 文の区切り判定

QdrantPoint = PointStruct | points_pb2.PointStruct


@dataclass
class IngestResult:
    """取り込み結果を表す簡単なモデル。"""

    total_chunks: int  # 登録されたチャンク総数
    collection_name: str  # 保存先 Qdrant コレクション名
    source_file: str  # ソースファイルのパス
    warnings: list[str] = field(default_factory=list)  # 警告メッセージリスト


class SimpleMarkdownSplitter:
    """
    シンプルな Markdown 分割クラス。

    方針:
    1. `#` と `##` 見出しで区切る。
    2. 各セクション本文を空行で区切る。
    3. ブロックを `chunk_size` までまとめる。
    4. 大きすぎるブロックは単純な区切りで再分割する。
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        # テキストを正規化し、セクション分割 → ブロック分割 → チャンク結合の順で処理
        normalized = self._normalize_text(text)
        if not normalized:
            return []

        chunks: list[str] = []
        for heading, body_lines in self._split_sections(normalized):
            blocks = self._split_blocks(body_lines)
            chunks.extend(self._pack_blocks(headings, blocks))
        return [chunk for chunk in chunks if chunk.strip()]

    def _normalize_text(self, text: str) -> str:
        # 改行コードを統一し、行末の空白を削除
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    def _split_sections(self, text: str) -> list[tuple[list[str], list[str]]]:
        # テキストを見出した構造のセクションに分割
        # 各セクションは (見出しパス, 本文行リスト) のタプルで表現
        sections: list[tuple[list[str], list[str]]] = []
        current_top_heading = ""
        current_path: list[str] = []
        current_body: list[str] = []

    def _split_blocks(self, lines: list[str]) -> list[str]:
        # 空行で区切られた本文をブロック単位に分割
        trimmed_lines = self._trim_blank_lines(lines)
        if not trimmed_lines:
            return []

        blocks: list[str] = []
        current_block: list[str] = []

        for line in trimmed_lines:
            if line.strip():
                current_block.append(line)
                continue

            if current_block:
                blocks.append("\n".join(current_block).strip())
                current_block = []

        if current_block:
            blocks.append("\n".join(current_block).strip())

        return blocks

    def _pack_blocks(self, headings: list[str], blocks: list[str]) -> list[str]:
        # ブロックを chunk_size に収まるようにまとめてチャンク化
        # 大きすぎるブロックまたは結合時は追加分割を試みる
        if not blocks:
            return []

        chunks: list[str] = []
        current_blocks: list[str] = []
