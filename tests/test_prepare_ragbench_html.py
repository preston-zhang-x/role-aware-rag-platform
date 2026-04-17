from pathlib import Path

from script import prepare_ragbench_html


def test_extract_document_text_supports_string_and_dict_payloads():
    assert prepare_ragbench_html.extract_document_text("alpha") == "alpha"
    assert (
        prepare_ragbench_html.extract_document_text({"text": "beta", "title": "ignored"})
        == "beta"
    )


def test_prepare_benchmark_artifacts_deduplicates_documents_and_writes_manifest(
    tmp_path: Path,
):
    rows = [
        {
            "id": "q1",
            "question": "What is alpha?",
            "response": "Alpha is first.",
            "documents": [
                "Alpha line 1\nAlpha line 2",
                {"content": "Shared doc body"},
            ],
        },
        {
            "id": "q2",
            "question": "What is shared?",
            "response": "Shared body.",
            "documents": [
                {"text": "Shared doc body"},
                "Standalone doc",
            ],
        },
    ]

    summary = prepare_ragbench_html.prepare_benchmark_artifacts(
        rows,
        output_root=tmp_path / "ragbench",
        subset="emanual",
    )

    docs = sorted(summary.docs_dir.glob("*.html"))
    manifest_lines = summary.manifest_path.read_text(encoding="utf-8").strip().splitlines()

    assert summary.question_count == 2
    assert summary.unique_document_count == 3
    assert len(docs) == 3
    assert len(manifest_lines) == 2

    first_doc = docs[0].read_text(encoding="utf-8")
    assert "<article>" in first_doc
    assert "<h1>rb_emanual_" in first_doc
    assert "<table" not in first_doc


def test_prepare_benchmark_artifacts_is_stable_across_runs(tmp_path: Path):
    rows = [
        {
            "id": "q1",
            "question": "What is alpha?",
            "response": "Alpha is first.",
            "documents": ["Alpha\n\nBeta"],
        }
    ]

    first = prepare_ragbench_html.prepare_benchmark_artifacts(
        rows,
        output_root=tmp_path / "ragbench",
        subset="emanual",
    )
    second = prepare_ragbench_html.prepare_benchmark_artifacts(
        rows,
        output_root=tmp_path / "ragbench",
        subset="emanual",
    )

    assert sorted(path.name for path in first.docs_dir.glob("*.html")) == sorted(
        path.name for path in second.docs_dir.glob("*.html")
    )
    assert first.manifest_path.read_text(encoding="utf-8") == second.manifest_path.read_text(
        encoding="utf-8"
    )
