"""LlamaIndex を使って文書を分割し、埋め込みを生成して Qdrant に保存する。"""

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from llama_index.core import Document
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client.http import models

from app.clients.qdrant_client import get_qdrant_client
from app.core.config import get_openai_settings
from app.services.bm25_service import invalidate_bm25_cache
from app.services.document_loader import DocumentLoader
from app.services.openai_compatible_embedding import OpenAICompatibleEmbedding

DEFAULT_COLLECTION = "documents"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
BATCH_SIZE = 64

_FORMULA_PATTERN = re.compile(
    r"\b(SUM|AVERAGE|COUNT|COUNTA|COUNTIF|COUNTIFS"
    r"|VLOOKUP|HLOOKUP|XLOOKUP|INDEX|MATCH"
    r"|IF|IFS|SUMIF|SUMIFS|SUMPRODUCT"
    r"|MAX|MIN|LEFT|RIGHT|MID|LEN|TRIM|CONCATENATE"
    r"|ROUND|ROUNDUP|ROUNDDOWN)\s*\(",
    re.IGNORECASE,
)


@dataclass
class IngestResult:
    """取り込み結果を表すシンプルなデータ。"""

    total_chunks: int
    collection_name: str
    source_file: str
    warnings: list[str] = field(default_factory=list)


class SimpleMarkdownSplitter:
    """
    `parse -> split -> embed -> store` の構成を維持する。
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> None:
        self._splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            include_metadata=False,
        )

    def split_text(self, text: str) -> list[str]:
        document = Document(text=self._normalize(text))
        return [node.text.strip() for node in self.split_document(document)]

    def split_document(self, document: Document) -> list[TextNode]:
        normalized = self._normalize(document.text or "")
        if not normalized:
            return []

        clean_document = Document(text=normalized, id_=document.id_)
        # テキストを分割してノードに変換する
        nodes = self._splitter.get_nodes_from_documents([clean_document])
        return [
            # テキストが空でないノードのみを返す
            node
            for node in nodes
            if isinstance(node, TextNode) and node.text.strip()
        ]

    def _normalize(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()


MarkdownAwareTextSplitter = SimpleMarkdownSplitter
RecursiveCharacterTextSplitter = SimpleMarkdownSplitter


def detect_formula_description(chunk_text: str) -> str | None:
    """チャンク内に Excel 関数らしき記述があれば短い説明を返す。"""
    found = set(_FORMULA_PATTERN.findall(chunk_text))
    if not found:
        return None

    names = ", ".join(sorted(found, key=str.upper))
    return f"この部分には Excel 関数（{names}）が含まれます"


class IngestService:
    """LlamaIndex ベースのシンプルな取り込みサービス。"""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        loader: DocumentLoader | None = None,
        splitter: SimpleMarkdownSplitter | None = None,
        qdrant_wrapper=None,
    ) -> None:
        self.collection_name = collection_name
        self.loader = loader or DocumentLoader()
        self.splitter = splitter or SimpleMarkdownSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.openai_settings = get_openai_settings()
        self.embedding_model = self.openai_settings.embedding_model
        self.qdrant_wrapper = qdrant_wrapper or get_qdrant_client()

    def ingest(self, file_path: str, allowed_roles: list[str]) -> IngestResult:
        # 1. 解析 2. 既存データ削除 3. 分割 4. 埋め込み 5. 保存
        parse_result = self.loader.load(file_path)
        invalidate_bm25_cache(self.collection_name)
        try:
            self._delete_existing_points(file_path)

            # 解析結果からテキストを取り出し、ノードを構築する。
            nodes = self._build_nodes(file_path, parse_result, allowed_roles)
            if not nodes:
                warnings = self._summarize_warnings(
                    parse_result.warnings
                    + ["ファイルから有効なテキストが抽出できませんでした、スキップ"]
                )
                return IngestResult(
                    total_chunks=0,
                    collection_name=self.collection_name,
                    source_file=file_path,
                    warnings=warnings,
                )

            pipeline = self._create_pipeline()
            embedded_nodes = list(pipeline.run(nodes=nodes))
            vector_store = self._create_vector_store()
            vector_store.add(embedded_nodes)

            return IngestResult(
                total_chunks=len(embedded_nodes),
                collection_name=self.collection_name,
                source_file=file_path,
                warnings=self._summarize_warnings(parse_result.warnings),
            )
        finally:
            invalidate_bm25_cache(self.collection_name)

    def _build_source_key(self, file_path: str) -> str:
        # ファイル単位で安定したキーを作る。

        return Path(file_path).resolve().as_posix()

    def _build_point_id(self, file_path: str, chunk_index: int) -> str:
        # 同じファイル・同じチャンクなら毎回同じ ID になるようにする。
        source_key = self._build_source_key(file_path)
        return str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{self.collection_name}:{source_key}:{chunk_index}",
            )
        )

    def _create_pipeline(self) -> IngestionPipeline:
        # 埋め込み生成だけを LlamaIndex の pipeline に任せる。
        embedding = OpenAICompatibleEmbedding(
            model_name=self.embedding_model,
            api_key=self.openai_settings.openai_api_key,
            api_base=self.openai_settings.openai_base_url,
            dimensions=self.openai_settings.embedding_dimensions,
            embed_batch_size=BATCH_SIZE,
        )
        return IngestionPipeline(transformations=[embedding])

    def _create_vector_store(self) -> QdrantVectorStore:
        # Qdrant への保存は公式の VectorStore 実装を使う。
        return QdrantVectorStore(
            collection_name=self.collection_name,
            client=self.qdrant_wrapper.client,
        )

    def _build_metadata(
        self,
        chunk_text: str,
        file_path: str,
        source_key: str,
        chunk_index: int,
        allowed_roles: list[str],
    ) -> dict[str, str | int | list[str]]:
        # 検索と権限制御のmetadataを構築する。
        metadata: dict[str, str | int | list[str]] = {
            "source_file": file_path,
            "source_key": source_key,
            "allowed_roles": allowed_roles,
            "chunk_index": chunk_index,
        }
        formula_desc = detect_formula_description(chunk_text)
        if formula_desc:
            metadata["formula_description"] = (
                formula_desc  # metadataにExcel関数の説明を追加する
            )
        return metadata

    def _summarize_warnings(self, warnings: list[str]) -> list[str]:
        # ingest の戻り値では同種 warning をまとめて扱いやすくする。
        grouped_counts: dict[str, int] = {}
        for warning in warnings:
            summary = self._warning_summary_key(warning)
            grouped_counts[summary] = grouped_counts.get(summary, 0) + 1
        return [f"{summary} ({count}件)" for summary, count in grouped_counts.items()]

    def _warning_summary_key(self, warning: str) -> str:
        if ": " in warning:
            return warning.split(": ", 1)[0]
        return warning

    def _build_nodes(
        self,
        file_path: str,
        parse_result,
        allowed_roles: list[str],
    ) -> list[TextNode]:
        # テキストを分割してノードに変換する。安定した source_key を付与する。
        source_key = self._build_source_key(file_path)
        document = Document(text=parse_result.text, id_=source_key)
        nodes = self.splitter.split_document(document)

        # チャンク位置からメタデータへのマップを構築
        chunk_position_map = []
        for chunk_meta in parse_result.chunks:
            if chunk_meta.sheet_name or chunk_meta.cell_range:
                chunk_position_map.append({
                    "start": chunk_meta.char_start,
                    "end": chunk_meta.char_end,
                    "sheet_name": chunk_meta.sheet_name,
                    "cell_range": chunk_meta.cell_range,
                    "content_type": chunk_meta.content_type.value if chunk_meta.content_type else None,
                })

        # 各ノードに安定 ID と検索用 metadata を付与する。
        search_start = 0
        for chunk_index, node in enumerate(nodes):
            chunk_text = node.text.strip()
            metadata = self._build_metadata(
                chunk_text=chunk_text,
                file_path=file_path,
                source_key=source_key,
                chunk_index=chunk_index,
                allowed_roles=allowed_roles,
            )

            # ノードのテキストが元のテキストのどこにあるかを検索
            node_start = parse_result.text.find(chunk_text, search_start)
            if node_start < 0:
                node_start = parse_result.text.find(chunk_text)
            if node_start >= 0:
                node_end = node_start + len(chunk_text)
                search_start = node_end

                best_chunk_info = self._select_best_overlapping_chunk(
                    node_start,
                    node_end,
                    chunk_position_map,
                )
                if best_chunk_info is not None:
                    for key in ["sheet_name", "cell_range", "content_type"]:
                        if best_chunk_info.get(key):
                            metadata[key] = best_chunk_info[key]

            node.id_ = self._build_point_id(file_path, chunk_index)
            node.text = chunk_text
            node.metadata = metadata
            node.excluded_embed_metadata_keys = list(metadata.keys())

        return nodes

    def _select_best_overlapping_chunk(
        self,
        node_start: int,
        node_end: int,
        chunk_position_map: list[dict[str, str | int | None]],
    ) -> dict[str, str | int | None] | None:
        """重なる parser chunk の中から最も代表性の高いものを選ぶ。"""
        best_chunk_info: dict[str, str | int | None] | None = None
        best_overlap = 0
        for chunk_info in chunk_position_map:
            start = int(chunk_info["start"])
            end = int(chunk_info["end"])
            overlap = min(node_end, end) - max(node_start, start)
            if overlap <= 0:
                continue
            if overlap > best_overlap:
                best_chunk_info = chunk_info
                best_overlap = overlap
        return best_chunk_info

    def _delete_existing_points(self, file_path: str) -> None:
        # 再取り込み時は同じファイル由来の古いデータを先に消す。
        if not self.qdrant_wrapper.collection_exists(self.collection_name):
            return

        source_key = self._build_source_key(file_path)
        # source_file と source_key の両方でマッチするポイントを削除するセレクタを作る。
        selector = models.FilterSelector(
            filter=models.Filter(
                should=[
                    models.FieldCondition(
                        key="source_file",
                        match=models.MatchValue(value=file_path),
                    ),
                    models.FieldCondition(
                        key="source_key",
                        match=models.MatchValue(value=source_key),
                    ),
                ]
            )
        )

        # Qdrant の delete API を使ってポイントを削除する。
        self.qdrant_wrapper.client.delete(
            collection_name=self.collection_name,
            points_selector=selector,
            wait=True,
        )
