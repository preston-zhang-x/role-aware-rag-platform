"""
比較用: 2 つの RAGBench JSON summary を並べて差分を見る軽量スクリプト。

使い方:
    python script/compare_ragbench_runs.py `
        --left docs/report_ragbench_emanual_hybrid.json `
        --right docs/report_ragbench_emanual_hybrid_rerank.json `
        --output-file docs/report_ragbench_compare.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from script.run_ragbench_eval import build_unique_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two RAGBench JSON summaries."
    )
    parser.add_argument("--left", required=True, help="Left JSON summary path.")
    parser.add_argument("--right", required=True, help="Right JSON summary path.")
    parser.add_argument(
        "--output-file",
        default=None,
        help="Optional markdown output path. Prints to stdout when omitted.",
    )
    return parser.parse_args()


def load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "unique_summary" not in payload or "unique_results" not in payload:
        unique_results, unique_summary = build_unique_summary(payload.get("results", []))
        payload["unique_results"] = unique_results
        payload["unique_summary"] = unique_summary
    return payload


def safe_metric(summary: dict[str, Any], key: str) -> float:
    return float(summary.get(key, 0.0) or 0.0)


def safe_unique_metric(summary: dict[str, Any], key: str) -> float:
    unique_summary = summary.get("unique_summary", {})
    return float(unique_summary.get(key, 0.0) or 0.0)


def build_unique_index(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in summary.get("unique_results", []):
        record_id = str(item.get("id") or "").strip()
        if record_id:
            index[record_id] = item
    return index


def format_delta(delta: float, *, suffix: str = "") -> str:
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.3f}{suffix}"


def generate_comparison_report(
    left_summary: dict[str, Any],
    right_summary: dict[str, Any],
) -> str:
    left_mode = str(left_summary.get("retrieval_mode") or "left")
    right_mode = str(right_summary.get("retrieval_mode") or "right")
    left_unique = left_summary.get("unique_summary", {})
    right_unique = right_summary.get("unique_summary", {})

    shared_ids = set(build_unique_index(left_summary)) & set(build_unique_index(right_summary))
    left_index = build_unique_index(left_summary)
    right_index = build_unique_index(right_summary)

    changed_rows: list[dict[str, Any]] = []
    for record_id in shared_ids:
        left_item = left_index[record_id]
        right_item = right_index[record_id]
        f1_delta = float(right_item["avg_answer_token_f1"]) - float(
            left_item["avg_answer_token_f1"]
        )
        if (
            left_item["hit_pattern"] != right_item["hit_pattern"]
            or abs(f1_delta) >= 0.02
        ):
            changed_rows.append(
                {
                    "id": record_id,
                    "question": right_item.get("question") or left_item.get("question") or "",
                    "left_hit_pattern": left_item["hit_pattern"],
                    "right_hit_pattern": right_item["hit_pattern"],
                    "left_avg_f1": float(left_item["avg_answer_token_f1"]),
                    "right_avg_f1": float(right_item["avg_answer_token_f1"]),
                    "delta_f1": f1_delta,
                }
            )

    changed_rows.sort(key=lambda item: abs(item["delta_f1"]), reverse=True)

    lines = [
        "# RAGBench Comparison",
        "",
        f"**Left Mode**: `{left_mode}`",
        f"**Right Mode**: `{right_mode}`",
        "",
        "## Overall Metrics",
        "",
        f"| Metric | {left_mode} | {right_mode} | Delta ({right_mode} - {left_mode}) |",
        "|--------|-------------|--------------|--------------------------------------|",
        f"| Accuracy | {safe_metric(left_summary, 'accuracy'):.1f}% | {safe_metric(right_summary, 'accuracy'):.1f}% | {format_delta(safe_metric(right_summary, 'accuracy') - safe_metric(left_summary, 'accuracy'), suffix='%')} |",
        f"| Source Hit Rate | {safe_metric(left_summary, 'source_hit_rate'):.1f}% | {safe_metric(right_summary, 'source_hit_rate'):.1f}% | {format_delta(safe_metric(right_summary, 'source_hit_rate') - safe_metric(left_summary, 'source_hit_rate'), suffix='%')} |",
        f"| Avg Source Recall | {safe_metric(left_summary, 'avg_source_recall'):.3f} | {safe_metric(right_summary, 'avg_source_recall'):.3f} | {format_delta(safe_metric(right_summary, 'avg_source_recall') - safe_metric(left_summary, 'avg_source_recall'))} |",
        f"| Avg Answer Token F1 | {safe_metric(left_summary, 'avg_answer_token_f1'):.3f} | {safe_metric(right_summary, 'avg_answer_token_f1'):.3f} | {format_delta(safe_metric(right_summary, 'avg_answer_token_f1') - safe_metric(left_summary, 'avg_answer_token_f1'))} |",
        f"| unique_any_hit | {int(left_unique.get('unique_any_hit', 0))} | {int(right_unique.get('unique_any_hit', 0))} | {format_delta(safe_unique_metric(right_summary, 'unique_any_hit') - safe_unique_metric(left_summary, 'unique_any_hit'))} |",
        f"| unique_both_hit | {int(left_unique.get('unique_both_hit', 0))} | {int(right_unique.get('unique_both_hit', 0))} | {format_delta(safe_unique_metric(right_summary, 'unique_both_hit') - safe_unique_metric(left_summary, 'unique_both_hit'))} |",
        f"| Avg Unique Answer Token F1 | {safe_unique_metric(left_summary, 'avg_unique_answer_token_f1'):.3f} | {safe_unique_metric(right_summary, 'avg_unique_answer_token_f1'):.3f} | {format_delta(safe_unique_metric(right_summary, 'avg_unique_answer_token_f1') - safe_unique_metric(left_summary, 'avg_unique_answer_token_f1'))} |",
        f"| Mode Internal Hit Flip Count | {int(left_unique.get('mode_internal_hit_flip_count', 0))} | {int(right_unique.get('mode_internal_hit_flip_count', 0))} | {format_delta(safe_unique_metric(right_summary, 'mode_internal_hit_flip_count') - safe_unique_metric(left_summary, 'mode_internal_hit_flip_count'))} |",
        "",
        "## Changed Unique Questions",
        "",
        f"| ID | Question | {left_mode} Hit Pattern | {right_mode} Hit Pattern | {left_mode} Avg F1 | {right_mode} Avg F1 | Delta F1 |",
        "|----|----------|-------------------------|--------------------------|----------------|-----------------|----------|",
    ]

    if changed_rows:
        for row in changed_rows[:20]:
            lines.append(
                "| "
                f"{row['id']} | "
                f"{str(row['question'])[:40]} | "
                f"{row['left_hit_pattern']} | "
                f"{row['right_hit_pattern']} | "
                f"{row['left_avg_f1']:.3f} | "
                f"{row['right_avg_f1']:.3f} | "
                f"{format_delta(row['delta_f1'])} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - |")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    left_path = Path(args.left)
    right_path = Path(args.right)
    output_file = Path(args.output_file) if args.output_file else None

    report = generate_comparison_report(
        load_summary(left_path),
        load_summary(right_path),
    )
    if output_file is None:
        print(report)
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(report, encoding="utf-8")
    print(f"Comparison report saved to {output_file}")


if __name__ == "__main__":
    main()
