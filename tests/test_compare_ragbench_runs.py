from __future__ import annotations

import json
from pathlib import Path

from script import compare_ragbench_runs


def test_load_summary_backfills_unique_fields(tmp_path: Path) -> None:
    payload = {
        "retrieval_mode": "hybrid",
        "results": [
            {
                "id": "q1",
                "question": "Q1",
                "hit": True,
                "source_hit": True,
                "first_source_file": "docs/a.html",
                "source_files": ["docs/a.html"],
                "source_recall": 1.0,
                "answer_token_f1": 0.6,
                "latency_ms": 10.0,
            }
        ],
    }
    path = tmp_path / "left.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = compare_ragbench_runs.load_summary(path)

    assert loaded["unique_summary"]["unique_total"] == 1
    assert loaded["unique_results"][0]["id"] == "q1"


def test_generate_comparison_report_includes_key_metrics() -> None:
    left = {
        "retrieval_mode": "hybrid",
        "accuracy": 89.4,
        "source_hit_rate": 100.0,
        "avg_source_recall": 0.828,
        "avg_answer_token_f1": 0.521,
        "unique_summary": {
            "unique_any_hit": 64,
            "unique_both_hit": 54,
            "avg_unique_answer_token_f1": 0.520,
            "mode_internal_hit_flip_count": 10,
        },
        "unique_results": [
            {
                "id": "emanual_333",
                "question": "Where is audio settings?",
                "hit_pattern": "TT",
                "avg_answer_token_f1": 0.46,
            }
        ],
    }
    right = {
        "retrieval_mode": "hybrid_rerank",
        "accuracy": 92.7,
        "source_hit_rate": 100.0,
        "avg_source_recall": 0.840,
        "avg_answer_token_f1": 0.551,
        "unique_summary": {
            "unique_any_hit": 65,
            "unique_both_hit": 58,
            "avg_unique_answer_token_f1": 0.545,
            "mode_internal_hit_flip_count": 8,
        },
        "unique_results": [
            {
                "id": "emanual_333",
                "question": "Where is audio settings?",
                "hit_pattern": "TF",
                "avg_answer_token_f1": 0.30,
            }
        ],
    }

    report = compare_ragbench_runs.generate_comparison_report(left, right)

    assert "RAGBench Comparison" in report
    assert "Accuracy" in report
    assert "unique_both_hit" in report
    assert "Mode Internal Hit Flip Count" in report
    assert "emanual_333" in report
    assert "+3.300%" in report
