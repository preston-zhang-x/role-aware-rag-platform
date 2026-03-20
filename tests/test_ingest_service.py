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
from app.services.parse_result import ParseResult


class FakeLoader(DocumentLoader):
    def __init__(self, text: str, warnings: Sequence[str] | None = None) -> None:
        self.text = text
        self.warnings = list(warnings or ["parser warning"])

    def load(self, file_path: str) -> ParseResult:
        return ParseResult(text=self.text, warnings=list(self.warnings))


class FakeSplitter(SimpleMarkdownSplitter):
    def __init__(self, chunks: Sequence[str]) -> None:
        self.chunks = list(chunks)

    def split_document(self, document: Document) -> list[TextNode]:
        return [TextNode(text=chunk) for chunk in self.chunks]


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

    def test_ingest_invalidates_bm25_cache_before_delete_and_in_finally(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
    ) -> None:
        events: list[str] = []
        monkeypatch.setattr(
            ingest_service_module,
            "invalidate_bm25_cache",
            lambda collection_name: events.append(f"invalidate:{collection_name}"),
        )
        ingest_service = build_service(
            monkeypatch,
            qdrant_wrapper=fake_qdrant_wrapper,
        )
        monkeypatch.setattr(
            ingest_service,
            "_delete_existing_points",
            lambda file_path: events.append(f"delete:{file_path}"),
        )

        ingest_service.ingest(
            file_path="data/fixtures/japanese_spec.xlsx",
            allowed_roles=["admin"],
        )

        assert events == [
            "invalidate:documents",
            "delete:data/fixtures/japanese_spec.xlsx",
            "invalidate:documents",
        ]

    def test_ingest_invalidates_bm25_cache_when_vector_store_add_fails(
        self,
        monkeypatch: MonkeyPatch,
        fake_qdrant_wrapper: FakeQdrantWrapper,
    ) -> None:
        events: list[str] = []

        class FailingVectorStore(FakeVectorStore):
            def add(self, nodes: Sequence[TextNode], **kwargs: Any) -> list[str]:
                super().add(nodes, **kwargs)
                events.append("add")
                raise RuntimeError("vector store add failed")

        monkeypatch.setattr(
            ingest_service_module,
            "invalidate_bm25_cache",
            lambda collection_name: events.append(f"invalidate:{collection_name}"),
        )
        ingest_service = build_service(
            monkeypatch,
            qdrant_wrapper=fake_qdrant_wrapper,
            vector_store=FailingVectorStore(),
        )
        monkeypatch.setattr(
            ingest_service,
            "_delete_existing_points",
            lambda file_path: events.append(f"delete:{file_path}"),
        )

        with pytest.raises(RuntimeError, match="vector store add failed"):
            ingest_service.ingest(
                file_path="data/fixtures/japanese_spec.xlsx",
                allowed_roles=["admin"],
            )

        assert events == [
            "invalidate:documents",
            "delete:data/fixtures/japanese_spec.xlsx",
            "add",
            "invalidate:documents",
        ]
