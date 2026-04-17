"""
RAGBench を HTML 文書群へ変換し、ingest / eval 用 manifest を生成する。

使い方:
    python script/prepare_ragbench_html.py
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DATASET_NAME = "galileo-ai/ragbench"
DEFAULT_SUBSET = "emanual"
DEFAULT_SPLIT = "test"
DEFAULT_OUTPUT_ROOT = Path("data") / "ragbench" / DEFAULT_SUBSET
DOCS_DIRNAME = "docs"
MANIFEST_FILENAME = "manifest.jsonl"

_DOCUMENT_KEYS = ("text", "content", "document", "body")
_LINE_BREAK_RE = re.compile(r"\r\n|\r")
_BLANK_LINE_RE = re.compile(r"\n\s*\n+")


@dataclass(frozen=True)
class PreparationSummary:
    question_count: int
    unique_document_count: int
    docs_dir: Path
    manifest_path: Path


def normalize_line_endings(text: str) -> str:
    return _LINE_BREAK_RE.sub("\n", text)


def normalize_document_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalize_line_endings(normalized)
    lines = [line.rstrip() for line in normalized.split("\n")]
    collapsed = "\n".join(lines)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def extract_document_text(document: Any) -> str:
    if isinstance(document, str):
        return document

    if isinstance(document, dict):
        for key in _DOCUMENT_KEYS:
            value = document.get(key)
            if isinstance(value, str) and value.strip():
                return value

        string_values = [
            value.strip()
            for value in document.values()
            if isinstance(value, str) and value.strip()
        ]
        if string_values:
            return "\n\n".join(string_values)

    raise ValueError(f"Unsupported document payload: {type(document).__name__}")


def split_paragraphs(text: str) -> list[str]:
    normalized = normalize_document_text(text)
    if not normalized:
        return []

    if _BLANK_LINE_RE.search(normalized):
        chunks = _BLANK_LINE_RE.split(normalized)
        paragraphs = [
            " ".join(line.strip() for line in chunk.split("\n") if line.strip())
            for chunk in chunks
        ]
    else:
        lines = [line.strip() for line in normalized.split("\n") if line.strip()]
        paragraphs = [" ".join(lines)] if lines else []

    return [paragraph for paragraph in paragraphs if paragraph]


def build_document_id(text: str, prefix: str) -> str:
    digest = hashlib.sha1(normalize_document_text(text).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def render_document_html(document_id: str, text: str) -> str:
    paragraphs = split_paragraphs(text)
    title = html.escape(document_id, quote=True)
    body = "\n".join(f"    <p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        f"    <title>{title}</title>\n"
        "  </head>\n"
        "  <body>\n"
        "    <article>\n"
        f"      <h1>{title}</h1>\n"
        f"{body}\n"
        "    </article>\n"
        "  </body>\n"
        "</html>\n"
    )


def load_ragbench_rows(
    dataset_name: str = DATASET_NAME,
    subset: str = DEFAULT_SUBSET,
    split: str = DEFAULT_SPLIT,
) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "The 'datasets' package is required to download RAGBench. "
            "Install it first, for example: uv add datasets"
        ) from exc

    dataset = load_dataset(dataset_name, subset, split=split)
    return [dict(row) for row in dataset]


def prepare_benchmark_artifacts(
    rows: Iterable[dict[str, Any]],
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    subset: str = DEFAULT_SUBSET,
) -> PreparationSummary:
    output_root = Path(output_root)
    docs_dir = output_root / DOCS_DIRNAME
    manifest_path = output_root / MANIFEST_FILENAME
    docs_dir.mkdir(parents=True, exist_ok=True)

    document_prefix = f"rb_{subset}"
    known_documents: dict[str, str] = {}
    manifest_records: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        question = str(row.get("question", "")).strip()
        gold_response = str(row.get("response", "")).strip()
        raw_documents = row.get("documents") or []
        if not question or not gold_response or not raw_documents:
            continue

        expected_source_files: list[str] = []
        for raw_document in raw_documents:
            document_text = extract_document_text(raw_document).strip()
            if not document_text:
                continue

            normalized_document = normalize_document_text(document_text)
            if not normalized_document:
                continue

            document_id = build_document_id(normalized_document, document_prefix)
            file_name = f"{document_id}.html"
            relative_source_path = (docs_dir / file_name).as_posix()

            if document_id not in known_documents:
                html_path = docs_dir / file_name
                html_path.write_text(
                    render_document_html(document_id, normalized_document),
                    encoding="utf-8",
                )
                known_documents[document_id] = relative_source_path

            expected_source_files.append(relative_source_path)

        expected_source_files = list(dict.fromkeys(expected_source_files))
        if not expected_source_files:
            continue

        manifest_records.append(
            {
                "id": row.get("id", index),
                "question": question,
                "gold_response": gold_response,
                "expected_source_files": expected_source_files,
            }
        )

    manifest_text = "\n".join(
        json.dumps(record, ensure_ascii=False) for record in manifest_records
    )
    manifest_path.write_text(
        manifest_text + ("\n" if manifest_text else ""),
        encoding="utf-8",
    )

    return PreparationSummary(
        question_count=len(manifest_records),
        unique_document_count=len(known_documents),
        docs_dir=docs_dir,
        manifest_path=manifest_path,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare RAGBench emanual documents as HTML files."
    )
    parser.add_argument("--dataset", default=DATASET_NAME, help="Hugging Face dataset id.")
    parser.add_argument("--subset", default=DEFAULT_SUBSET, help="Dataset subset/config.")
    parser.add_argument("--split", default=DEFAULT_SPLIT, help="Dataset split.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Output directory for HTML docs and manifest.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    rows = load_ragbench_rows(
        dataset_name=args.dataset,
        subset=args.subset,
        split=args.split,
    )
    summary = prepare_benchmark_artifacts(
        rows,
        output_root=Path(args.output_root),
        subset=args.subset,
    )

    print(
        f"Prepared {summary.question_count} questions and "
        f"{summary.unique_document_count} unique HTML documents."
    )
    print(f"Docs directory: {summary.docs_dir}")
    print(f"Manifest: {summary.manifest_path}")


if __name__ == "__main__":
    main()
