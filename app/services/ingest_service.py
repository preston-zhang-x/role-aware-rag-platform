"""LlamaIndex を使って文書を分割し、埋め込みを生成して Qdrant に保存する。"""

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from llama_index.core import Document
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client.http import models

from app.clients.qdrant_client import get_qdrant_client
from app.core.config import openai_settings
from app.services.document_loader import DocumentLoader

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
        nodes = self._splitter.get_nodes_from_documents([clean_document])
        return [
            node for node in nodes if isinstance(node, TextNode) and node.text.strip()
        ]

    def _normalize(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()
