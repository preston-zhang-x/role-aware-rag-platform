"""
Excel を Qdrant に取り込むための簡易スクリプト。

使い方:
    python script/ingest_repo_spec.py
    python script/ingest_repo_spec.py --file docs/role_aware_rag_platform_spec.xlsx
    python script/ingest_repo_spec.py --file docs/a.xlsx docs/b.xlsx
    python script/ingest_repo_spec.py --dir docs --pattern *.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def collect_target_files(
    files: list[str] | None,
    directory: str | None,
    pattern: str,
    recursive: bool,
) -> list[Path]:
    use_default_file = not files and not directory
    targets: list[Path] = []

    if files:
        targets.extend(Path(file_path) for file_path in files)

    if directory:
        directory_path = Path(directory)
        if not directory_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        if not directory_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        iterator = (
            directory_path.rglob(pattern) if recursive else directory_path.glob(pattern)
        )
        targets.extend(sorted(path for path in iterator if path.is_file()))

    if use_default_file and not targets:
        targets.append(Path("docs/role_aware_rag_platform_spec.xlsx"))

    unique_targets: list[Path] = []
    seen: set[str] = set()
    for path in targets:
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise IsADirectoryError(f"Expected a file but got directory: {path}")
        seen.add(resolved)
        unique_targets.append(path)

    if not unique_targets:
        if directory:
            raise FileNotFoundError(
                f"No files matched pattern '{pattern}' under directory: {directory}"
            )
        if files:
            raise FileNotFoundError("No valid input files were provided.")

    return unique_targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest spec workbook into Qdrant.")
    parser.add_argument(
        "--file",
        nargs="+",
        help="Path(s) to one or more Excel files to ingest.",
    )
    parser.add_argument(
        "--dir",
        help="Directory containing Excel files to ingest.",
    )
    parser.add_argument(
        "--pattern",
        default="*.xlsx",
        help="Glob pattern used with --dir. Defaults to '*.xlsx'.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search subdirectories when --dir is specified.",
    )
    parser.add_argument(
        "--collection",
        default="documents",
        help="Qdrant collection name. Defaults to 'documents'.",
    )
    args = parser.parse_args()

    try:
        target_files = collect_target_files(
            files=args.file,
            directory=args.dir,
            pattern=args.pattern,
            recursive=args.recursive,
        )
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError) as exc:
        parser.error(str(exc))

    from app.services.ingest_service import IngestService

    service = IngestService(collection_name=args.collection)
    results = []
    for index, file_path in enumerate(target_files, start=1):
        print(f"[{index}/{len(target_files)}] ingesting: {file_path}")
        result = service.ingest(
            file_path=str(file_path),
            allowed_roles=["admin", "manager", "staff"],
        )
        results.append(result)

        print("=" * 60)
        print("Ingest done")
        print(f"collection: {result.collection_name}")
        print(f"chunks: {result.total_chunks}")
        print(f"source: {result.source_file}")
        if result.warnings:
            print("warnings:")
            for warning in result.warnings:
                print(f" - {warning}")
        print("=" * 60)

    print(
        f"Completed {len(results)} file(s), total chunks: "
        f"{sum(result.total_chunks for result in results)}"
    )


if __name__ == "__main__":
    main()
