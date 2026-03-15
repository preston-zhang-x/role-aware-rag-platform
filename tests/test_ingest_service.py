from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Sequence

import pytest
from _pytest.monkeypatch import MonkeyPatch
from llama_index.core import Document
from llama_index.core.schema import TextNode

import app.services.ingest_service as ingest_service_module
from app.services.document_loader import DocumentLoader
from app.services.ingest_service import IngestService, SimpleMarkdownSplitter
from app.services.parse_result import (
    BlockKind,
    ChunkMeta,
    ContentType,
    ParseResult,
    ParsedBlock,
)


class FakeLoader(DocumentLoader):
    def __init__(self, text: str, warnings: Sequence[str] | None = None) -> None:
        self.text = text
        self.warnings = list(warnings or ["parser warning"])

    def load(self, file_path: str) -> ParseResult:
        return ParseResult(text=self.text, warnings=list(self.warnings))


class FakeBlockLoader(DocumentLoader):
    def __init__(
        self,
        *,
        text: str = "fallback text",
        blocks: Sequence[ParsedBlock] | None = None,
        warnings: Sequence[str] | None = None,
    ) -> None:
        self.text = text
        self.blocks = list(blocks or [])
        self.warnings = list(warnings or [])

    def load(self, file_path: str) -> ParseResult:
        return ParseResult(
            text=self.text,
            blocks=list(self.blocks),
            warnings=list(self.warnings),
        )


class FakeSplitter(SimpleMarkdownSplitter):
    def __init__(self, chunks: Sequence[str]) -> None:
        self.chunks = list(chunks)

    def split_document(self, document: Document) -> list[TextNode]:
        return [TextNode(text=chunk) for chunk in self.chunks]


class EchoSplitter(SimpleMarkdownSplitter):
    def split_document(self, document: Document) -> list[TextNode]:
        text = document.text or ""
        return [TextNode(text=text)] if text.strip() else []


class FakePipeline:
    def run(
        self,
        *,
        nodes: Sequence[TextNode] | None = None,
        **kwargs: Any,
    ) -> list[TextNode]:
        embedded_nodes = list(nodes or [])
        for index, node in enumerate(embedded_nodes):
            node.embedding = [float(index), float(index) + 0.5]
        return embedded_nodes


@dataclass
class AddCall:
    nodes: list[TextNode]
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakeVectorStore:
    def __init__(self) -> None:
        self.add_calls: list[AddCall] = []

    def add(self, nodes: Sequence[TextNode], **kwargs: Any) -> list[str]:
        stored_nodes = list(nodes)
        self.add_calls.append(AddCall(nodes=stored_nodes, kwargs=dict(kwargs)))
        return [str(node.node_id) for node in stored_nodes]


class FakeQdrantClient:
    def __init__(self) -> None:
        self.delete_calls: list[dict[str, Any]] = []

    def delete(self, **kwargs: Any) -> SimpleNamespace:
        self.delete_calls.append(dict(kwargs))
        return SimpleNamespace(status="acknowledged")


class FakeQdrantWrapper:
    def __init__(self, exists: bool = True) -> None:
        self.client = FakeQdrantClient()
        self.exists = exists

    def collection_exists(self, collection_name: str) -> bool:
        return self.exists


def build_service(
    monkeypatch: MonkeyPatch,
    *,
    loader: FakeLoader | None = None,
    splitter: FakeSplitter | None = None,
    qdrant_wrapper: FakeQdrantWrapper | None = None,
    vector_store: FakeVectorStore | None = None,
) -> IngestService:
    ingest_service = IngestService(
        collection_name="documents",
        loader=loader or FakeLoader("ignored"),
        splitter=splitter or FakeSplitter(["chunk one", "chunk two"]),
        qdrant_wrapper=qdrant_wrapper or FakeQdrantWrapper(),
    )
    monkeypatch.setattr(ingest_service, "_create_pipeline", lambda: FakePipeline())
    monkeypatch.setattr(
        ingest_service,
        "_create_vector_store",
        lambda: vector_store or FakeVectorStore(),
    )
    return ingest_service


@pytest.fixture
def fake_qdrant_wrapper() -> FakeQdrantWrapper:
    return FakeQdrantWrapper()


@pytest.fixture
def fake_vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture
def service(
    monkeypatch: MonkeyPatch,
    fake_qdrant_wrapper: FakeQdrantWrapper,
    fake_vector_store: FakeVectorStore,
) -> IngestService:
    return build_service(
        monkeypatch,
        qdrant_wrapper=fake_qdrant_wrapper,
        vector_store=fake_vector_store,
    )


class TestSimpleMarkdownSplitter:
    def test_short_text_stays_in_one_chunk(self) -> None:
        splitter = SimpleMarkdownSplitter(chunk_size=100, chunk_overlap=10)
        chunks = splitter.split_text("# Overview\n\nThis is a small document.")

        assert len(chunks) == 1
        assert "# Overview" in chunks[0]

    def test_long_text_is_split(self) -> None:
        text = " ".join(["This is a sentence."] * 80)

        splitter = SimpleMarkdownSplitter(chunk_size=20, chunk_overlap=5)
        chunks = splitter.split_text(text)

        assert len(chunks) > 1
        assert all(chunk.strip() for chunk in chunks)

    def test_blank_text_returns_empty_list(self) -> None:
        splitter = SimpleMarkdownSplitter()
        assert splitter.split_text(" \n\n ") == []


class TestStablePointId:
    def test_point_id_is_deterministic(self, service: IngestService) -> None:
        file_path = "data/fixtures/japanese_spec.xlsx"
        first = service._build_point_id(file_path, 0)
        second = service._build_point_id(file_path, 0)
        third = service._build_point_id(file_path, 1)

        assert first == second
        assert first != third


class TestFactories:
    def test_create_pipeline_uses_openai_settings(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
    ) -> None:
        captured: dict[str, Any] = {}

        class FakeEmbedding:
            def __init__(self, **kwargs: Any) -> None:
                captured["embedding_kwargs"] = kwargs

        class FakePipelineFactory:
            def __init__(self, transformations: list[object]) -> None:
                captured["transformations"] = transformations
                self.transformations = transformations

        monkeypatch.setattr(ingest_service_module, "OpenAIEmbedding", FakeEmbedding)
        monkeypatch.setattr(
            ingest_service_module,
            "IngestionPipeline",
            FakePipelineFactory,
        )

        ingest_service = IngestService(
            collection_name="documents",
            loader=FakeLoader("chunk one"),
            splitter=FakeSplitter(["chunk one"]),
            qdrant_wrapper=fake_qdrant_wrapper,
        )

        pipeline = ingest_service._create_pipeline()

        assert isinstance(pipeline, FakePipelineFactory)
        assert len(pipeline.transformations) == 1
        assert captured["transformations"] == pipeline.transformations
        assert captured["embedding_kwargs"] == {
            "model": ingest_service.embedding_model,
            "api_key": ingest_service_module.openai_settings.openai_api_key,
            "api_base": ingest_service_module.openai_settings.openai_base_url,
            "dimensions": ingest_service_module.openai_settings.embedding_dimensions,
            "embed_batch_size": ingest_service_module.BATCH_SIZE,
        }

    def test_create_vector_store_uses_current_collection_and_client(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
    ) -> None:
        captured: dict[str, Any] = {}

        class FakeQdrantVectorStore:
            def __init__(self, **kwargs: Any) -> None:
                captured["vector_store_kwargs"] = kwargs

        monkeypatch.setattr(
            ingest_service_module,
            "QdrantVectorStore",
            FakeQdrantVectorStore,
        )

        ingest_service = IngestService(
            collection_name="documents",
            loader=FakeLoader("chunk one"),
            splitter=FakeSplitter(["chunk one"]),
            qdrant_wrapper=fake_qdrant_wrapper,
        )

        vector_store = ingest_service._create_vector_store()

        assert isinstance(vector_store, FakeQdrantVectorStore)
        assert captured["vector_store_kwargs"] == {
            "collection_name": "documents",
            "client": fake_qdrant_wrapper.client,
        }


class TestIngestWithLlamaIndex:
    def test_warning_summary_groups_by_prefix_and_preserves_order(
        self,
        service: IngestService,
    ) -> None:
        warnings = [
            "結合セルの値をブロードキャスト展開しました: A1:C1",
            "非表示シートをスキップしました: hidden_1",
            "結合セルの値をブロードキャスト展開しました: A2:C2",
            "parser warning",
            "parser warning",
        ]

        assert service._summarize_warnings(warnings) == [
            "結合セルの値をブロードキャスト展開しました (2件)",
            "非表示シートをスキップしました (1件)",
            "parser warning (2件)",
        ]

    def test_ingest_deletes_existing_source_points(
        self,
        service: IngestService,
        fake_qdrant_wrapper: FakeQdrantWrapper,
    ) -> None:
        file_path = "data/fixtures/japanese_spec.xlsx"

        service.ingest(file_path=file_path, allowed_roles=["admin", "staff"])

        assert len(fake_qdrant_wrapper.client.delete_calls) == 1
        delete_call = fake_qdrant_wrapper.client.delete_calls[0]
        points_selector = delete_call["points_selector"]
        filter_conditions = points_selector.filter.should
        assert filter_conditions is not None
        matched_keys = {condition.key for condition in filter_conditions}
        assert matched_keys == {"source_file", "source_key"}

    def test_ingest_uses_stable_node_ids_across_runs(
        self,
        service: IngestService,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        file_path = "data/fixtures/japanese_spec.xlsx"

        first_result = service.ingest(file_path=file_path, allowed_roles=["admin"])
        second_result = service.ingest(file_path=file_path, allowed_roles=["admin"])

        assert first_result.total_chunks == 2
        assert second_result.total_chunks == 2
        assert len(fake_vector_store.add_calls) == 2

        first_nodes = fake_vector_store.add_calls[0].nodes
        second_nodes = fake_vector_store.add_calls[1].nodes

        assert [node.node_id for node in first_nodes] == [
            node.node_id for node in second_nodes
        ]
        metadata = first_nodes[0].metadata
        assert metadata is not None
        assert metadata["source_key"] == service._build_source_key(file_path)
        assert metadata["chunk_index"] == 0
        second_metadata = first_nodes[1].metadata
        assert second_metadata is not None
        assert second_metadata["chunk_index"] == 1

    def test_ingest_metadata_keeps_expected_keys(
        self,
        service: IngestService,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        file_path = "data/fixtures/japanese_spec.xlsx"

        service.ingest(file_path=file_path, allowed_roles=["admin", "staff"])

        nodes = fake_vector_store.add_calls[0].nodes
        metadata = nodes[0].metadata
        assert metadata is not None

        assert {
            "source_file",
            "source_key",
            "allowed_roles",
            "chunk_index",
        } <= set(metadata)
        assert "text" not in metadata
        assert "text" not in nodes[0].excluded_embed_metadata_keys
        assert nodes[0].embedding == [0.0, 0.5]

    def test_ingest_prefers_blocks_when_available(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        blocks = [
            ParsedBlock(
                text="## IF-007\n- Method: DELETE",
                meta=ChunkMeta(
                    source_file="docs/spec.xlsx",
                    content_type=ContentType.KEY_VALUE,
                    sheet_name="IF一覧",
                    block_kind=BlockKind.RECORD_SUMMARY,
                    record_id="IF-007",
                    record_type="IF",
                    related_ids=["FN-007"],
                ),
            ),
            ParsedBlock(
                text="## IF-005 / Path\n- 項目名: doc_id",
                meta=ChunkMeta(
                    source_file="docs/spec.xlsx",
                    content_type=ContentType.KEY_VALUE,
                    sheet_name="IF仕様",
                    block_kind=BlockKind.RECORD_SECTION,
                    record_id="IF-005",
                    record_type="IF",
                    section_name="Path",
                ),
            ),
        ]
        ingest_service = build_service(
            monkeypatch,
            loader=FakeBlockLoader(text="legacy text", blocks=blocks),
            splitter=EchoSplitter(),
            qdrant_wrapper=fake_qdrant_wrapper,
            vector_store=fake_vector_store,
        )

        result = ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        assert result.total_chunks == 2
        nodes = fake_vector_store.add_calls[0].nodes
        assert nodes[0].text == "## IF-007\n- Method: DELETE"
        assert nodes[1].text == "## IF-005 / Path\n- 項目名: doc_id"

    def test_ingest_block_metadata_is_written_to_payload(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        block = ParsedBlock(
            text="## COL-TBL-002-005\n- parent_record_id: TBL-002",
            meta=ChunkMeta(
                source_file="docs/spec.xlsx",
                content_type=ContentType.KEY_VALUE,
                sheet_name="テーブル定義",
                cell_range="A20:L20",
                block_kind=BlockKind.RECORD_ROW,
                record_id="COL-TBL-002-005",
                parent_record_id="TBL-002",
                record_type="COL",
                section_name=None,
                related_ids=["TBL-002"],
            ),
        )
        ingest_service = build_service(
            monkeypatch,
            loader=FakeBlockLoader(blocks=[block]),
            splitter=EchoSplitter(),
            qdrant_wrapper=fake_qdrant_wrapper,
            vector_store=fake_vector_store,
        )

        ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        metadata = fake_vector_store.add_calls[0].nodes[0].metadata
        assert metadata is not None
        assert metadata["sheet_name"] == "テーブル定義"
        assert metadata["cell_range"] == "A20:L20"
        assert metadata["block_kind"] == "record_row"
        assert metadata["record_id"] == "COL-TBL-002-005"
        assert metadata["parent_record_id"] == "TBL-002"
        assert metadata["record_type"] == "COL"
        assert metadata["related_ids"] == ["TBL-002"]

    def test_ingest_falls_back_to_text_when_blocks_are_absent(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        ingest_service = build_service(
            monkeypatch,
            loader=FakeBlockLoader(text="legacy fallback text", blocks=[]),
            splitter=FakeSplitter(["legacy fallback text"]),
            qdrant_wrapper=fake_qdrant_wrapper,
            vector_store=fake_vector_store,
        )

        result = ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        assert result.total_chunks == 1
        nodes = fake_vector_store.add_calls[0].nodes
        assert nodes[0].text == "legacy fallback text"

    def test_block_based_ingest_keeps_stable_chunk_order_across_runs(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        blocks = [
            ParsedBlock(
                text="## CFG-001\n- コード既定値: -",
                meta=ChunkMeta(
                    source_file="docs/spec.xlsx",
                    content_type=ContentType.KEY_VALUE,
                    block_kind=BlockKind.RECORD_SUMMARY,
                    record_id="CFG-001",
                    record_type="CFG",
                ),
            ),
            ParsedBlock(
                text="## CFG-002\n- コード既定値: HS256",
                meta=ChunkMeta(
                    source_file="docs/spec.xlsx",
                    content_type=ContentType.KEY_VALUE,
                    block_kind=BlockKind.RECORD_SUMMARY,
                    record_id="CFG-002",
                    record_type="CFG",
                ),
            ),
        ]
        ingest_service = build_service(
            monkeypatch,
            loader=FakeBlockLoader(blocks=blocks),
            splitter=EchoSplitter(),
            qdrant_wrapper=fake_qdrant_wrapper,
            vector_store=fake_vector_store,
        )

        first = ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )
        second = ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        assert first.total_chunks == 2
        assert second.total_chunks == 2
        first_nodes = fake_vector_store.add_calls[0].nodes
        second_nodes = fake_vector_store.add_calls[1].nodes
        assert [node.node_id for node in first_nodes] == [
            node.node_id for node in second_nodes
        ]
        assert [node.metadata["record_id"] for node in first_nodes] == [
            "CFG-001",
            "CFG-002",
        ]

    def test_ingest_returns_summarized_warnings(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
    ) -> None:
        ingest_service = build_service(
            monkeypatch,
            loader=FakeLoader(
                "chunk one",
                warnings=[
                    "結合セルの値をブロードキャスト展開しました: A1:C1",
                    "結合セルの値をブロードキャスト展開しました: A2:C2",
                    "parser warning",
                ],
            ),
            splitter=FakeSplitter(["chunk one"]),
            qdrant_wrapper=fake_qdrant_wrapper,
        )

        result = ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        assert result.warnings == [
            "結合セルの値をブロードキャスト展開しました (2件)",
            "parser warning (1件)",
        ]

    def test_ingest_adds_formula_description_when_needed(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        ingest_service = build_service(
            monkeypatch,
            loader=FakeLoader("SUM(A1:A10)"),
            splitter=FakeSplitter(["SUM(A1:A10)"]),
            qdrant_wrapper=fake_qdrant_wrapper,
            vector_store=fake_vector_store,
        )

        ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        metadata = fake_vector_store.add_calls[0].nodes[0].metadata
        assert metadata is not None
        assert "formula_description" in metadata
        assert "SUM" in metadata["formula_description"]

    def test_ingest_returns_skip_warning_for_empty_text(
        self,
        monkeypatch: MonkeyPatch,
        fake_vector_store: FakeVectorStore,
    ) -> None:
        ingest_service = build_service(
            monkeypatch,
            loader=FakeLoader(""),
            splitter=FakeSplitter([]),
            qdrant_wrapper=FakeQdrantWrapper(exists=False),
            vector_store=fake_vector_store,
        )

        result = ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        assert result.total_chunks == 0
        assert result.warnings == [
            "parser warning (1件)",
            "ファイルから有効なテキストが抽出できませんでした、スキップ (1件)",
        ]
        assert fake_vector_store.add_calls == []
