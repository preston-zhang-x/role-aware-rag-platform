import json
from pathlib import Path

import httpx
import pytest

from script import run_ragbench_eval


def make_response(
    url: str,
    *,
    status_code: int = 200,
    json_data: dict | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", url),
        json=json_data or {},
    )


def test_compute_token_f1_normalizes_text():
    score = run_ragbench_eval.compute_token_f1(
        "Ｔｏｋｅｎ type is Bearer",
        "token type bearer",
    )

    assert score > 0.8


def test_evaluate_sources_returns_hit_and_recall():
    source_hit, source_recall = run_ragbench_eval.evaluate_sources(
        [
            {"source_file": "data/ragbench/emanual/docs/a.html"},
            {"source_file": "data/ragbench/emanual/docs/x.html"},
        ],
        [
            "data/ragbench/emanual/docs/a.html",
            "data/ragbench/emanual/docs/b.html",
        ],
    )

    assert source_hit is True
    assert source_recall == 0.5


def test_evaluate_sources_normalizes_windows_and_posix_paths():
    source_hit, source_recall = run_ragbench_eval.evaluate_sources(
        [
            {"source_file": "data\\ragbench\\emanual\\docs\\a.html"},
        ],
        [
            "data/ragbench/emanual/docs/a.html",
        ],
    )

    assert source_hit is True
    assert source_recall == 1.0


def test_run_eval_logs_in_once_and_computes_metrics(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EVAL_ADMIN_USERNAME", "admin1")
    monkeypatch.setenv("EVAL_ADMIN_PASSWORD", "password123")
    monkeypatch.setattr(
        run_ragbench_eval,
        "load_manifest_records",
        lambda path=None: [
            {
                "id": "q1",
                "question": "Q1",
                "gold_response": "alpha bearer token",
                "expected_source_files": ["data/ragbench/emanual/docs/a.html"],
            },
            {
                "id": "q2",
                "question": "Q2",
                "gold_response": "beta second",
                "expected_source_files": ["data/ragbench/emanual/docs/b.html"],
            },
        ],
    )

    calls: list[tuple[str, dict]] = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        if url == run_ragbench_eval.AUTH_API_URL:
            return make_response(
                url,
                json_data={"access_token": "test-token", "token_type": "bearer"},
            )

        assert kwargs["headers"]["Authorization"] == "Bearer test-token"
        question = kwargs["json"]["question"]
        if question == "Q1":
            return make_response(
                url,
                json_data={
                    "answer": "alpha bearer token",
                    "sources": [
                        {
                            "source_file": "data/ragbench/emanual/docs/a.html",
                            "text": "matched source",
                            "score": 0.9,
                            "chunk_index": 0,
                        }
                    ],
                    "metadata": {"latency_ms": 12.5},
                },
            )

        return make_response(
            url,
            json_data={
                "answer": "wrong answer",
                "sources": [
                    {
                        "source_file": "data/ragbench/emanual/docs/x.html",
                        "text": "other source",
                        "score": 0.4,
                        "chunk_index": 1,
                    }
                ],
                "metadata": {"latency_ms": 9.0},
            },
        )

    monkeypatch.setattr(run_ragbench_eval.httpx, "post", fake_post)
    monkeypatch.setattr(
        run_ragbench_eval,
        "get_retrieval_settings",
        lambda: type("Settings", (), {"retrieval_mode": "vector"})(),
    )

    summary = run_ragbench_eval.run_eval(Path("ignored.jsonl"))

    auth_calls = [url for url, _ in calls if url == run_ragbench_eval.AUTH_API_URL]
    rag_calls = [url for url, _ in calls if url == run_ragbench_eval.RAG_API_URL]

    assert len(auth_calls) == 1
    assert len(rag_calls) == 2
    assert summary["hit"] == 1
    assert summary["source_hit_rate"] == 50.0
    assert summary["avg_source_recall"] == 0.5
    assert summary["avg_answer_token_f1"] < 1.0
    assert summary["results"][0]["source_files"] == [
        "data/ragbench/emanual/docs/a.html"
    ]
    assert summary["unique_summary"]["unique_total"] == 2
    assert summary["unique_summary"]["unique_any_hit"] == 1
    assert summary["unique_summary"]["unique_both_hit"] == 1
    assert summary["unique_summary"]["mode_internal_hit_flip_count"] == 0


def test_run_eval_reauthenticates_once_after_401(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EVAL_ADMIN_USERNAME", "admin1")
    monkeypatch.setenv("EVAL_ADMIN_PASSWORD", "password123")
    monkeypatch.setattr(
        run_ragbench_eval,
        "load_manifest_records",
        lambda path=None: [
            {
                "id": "q1",
                "question": "Q1",
                "gold_response": "alpha bearer token",
                "expected_source_files": ["data/ragbench/emanual/docs/a.html"],
            }
        ],
    )

    token_counter = {"count": 0}

    def fake_post(url: str, **kwargs):
        if url == run_ragbench_eval.AUTH_API_URL:
            token_counter["count"] += 1
            return make_response(
                url,
                json_data={
                    "access_token": f"test-token-{token_counter['count']}",
                    "token_type": "bearer",
                },
            )

        auth_header = kwargs["headers"]["Authorization"]
        if auth_header == "Bearer test-token-1":
            return make_response(
                url,
                status_code=401,
                json_data={"detail": "Could not validate credentials"},
            )

        assert auth_header == "Bearer test-token-2"
        return make_response(
            url,
            json_data={
                "answer": "alpha bearer token",
                "sources": [
                    {
                        "source_file": "data/ragbench/emanual/docs/a.html",
                        "text": "matched source",
                        "score": 0.9,
                        "chunk_index": 0,
                    }
                ],
                "metadata": {"latency_ms": 12.5},
            },
        )

    monkeypatch.setattr(run_ragbench_eval.httpx, "post", fake_post)
    monkeypatch.setattr(
        run_ragbench_eval,
        "get_retrieval_settings",
        lambda: type("Settings", (), {"retrieval_mode": "vector"})(),
    )

    summary = run_ragbench_eval.run_eval(Path("ignored.jsonl"))

    assert token_counter["count"] == 2
    assert summary["hit"] == 1
    assert summary["error"] == 0


def test_build_unique_summary_detects_duplicate_flip_and_source_order_change():
    unique_results, unique_summary = run_ragbench_eval.build_unique_summary(
        [
            {
                "id": "q1",
                "question": "Q1",
                "hit": True,
                "source_hit": True,
                "first_source_file": "docs/a.html",
                "source_files": ["docs/a.html", "docs/b.html"],
                "source_recall": 1.0,
                "answer_token_f1": 0.8,
                "latency_ms": 10.0,
            },
            {
                "id": "q1",
                "question": "Q1",
                "hit": False,
                "source_hit": True,
                "first_source_file": "docs/a.html",
                "source_files": ["docs/a.html", "docs/c.html"],
                "source_recall": 1.0,
                "answer_token_f1": 0.2,
                "latency_ms": 12.0,
            },
        ]
    )

    assert len(unique_results) == 1
    assert unique_results[0]["hit_pattern"] == "TF"
    assert unique_results[0]["source_order_flip"] is True
    assert unique_summary["unique_total"] == 1
    assert unique_summary["unique_any_hit"] == 1
    assert unique_summary["unique_both_hit"] == 0
    assert unique_summary["mode_internal_hit_flip_count"] == 1
    assert unique_summary["mode_internal_first_source_flip_count"] == 0
    assert unique_summary["mode_internal_source_order_flip_count"] == 1


def test_save_summary_json_writes_file(tmp_path: Path):
    output_path = tmp_path / "summary.json"
    summary = {"retrieval_mode": "hybrid", "unique_summary": {"unique_total": 1}}

    run_ragbench_eval.save_summary_json(summary, output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["retrieval_mode"] == "hybrid"
    assert saved["unique_summary"]["unique_total"] == 1


def test_generate_report_includes_required_sections():
    summary = {
        "total": 1,
        "hit": 1,
        "miss": 0,
        "error": 0,
        "accuracy": 100.0,
        "source_hit_rate": 100.0,
        "avg_source_recall": 1.0,
        "avg_answer_token_f1": 0.9,
        "execution_mode": "admin-only ragbench evaluation",
        "executed_as": "admin",
        "retrieval_mode": "vector",
        "unique_summary": {
            "unique_total": 1,
            "unique_any_hit": 1,
            "unique_both_hit": 1,
            "mode_internal_hit_flip_count": 0,
            "mode_internal_source_hit_flip_count": 0,
            "mode_internal_first_source_flip_count": 0,
            "mode_internal_source_order_flip_count": 0,
            "avg_unique_source_recall": 1.0,
            "avg_unique_answer_token_f1": 0.9,
            "avg_unique_latency_ms": 10.0,
        },
        "unique_results": [
            {
                "id": "q1",
                "question": "What is alpha?",
                "runs": 1,
                "hit_pattern": "T",
                "source_hit_pattern": "T",
                "any_hit": True,
                "both_hit": True,
                "hit_flip": False,
                "source_hit_flip": False,
                "first_source_flip": False,
                "source_order_flip": False,
                "avg_answer_token_f1": 0.9,
                "avg_source_recall": 1.0,
                "avg_latency_ms": 10.0,
            }
        ],
        "error_breakdown": {},
        "results": [
            {
                "id": "q1",
                "question": "What is alpha?",
                "gold_response": "Alpha is first.",
                "expected_source_files": ["data/ragbench/emanual/docs/a.html"],
                "executed_as": "admin",
                "answer": "Alpha is first.",
                "sources_count": 1,
                "source_files": ["data/ragbench/emanual/docs/a.html"],
                "first_source_file": "data/ragbench/emanual/docs/a.html",
                "source_hit": True,
                "source_recall": 1.0,
                "answer_token_f1": 0.9,
                "latency_ms": 10.0,
                "hit": True,
                "error": None,
                "error_reason": None,
            }
        ],
    }

    report = run_ragbench_eval.generate_report(summary)

    assert "Source Hit Rate" in report
    assert "Avg Source Recall" in report
    assert "Avg Answer Token F1" in report
    assert "Unique Question Summary" in report
    assert "Duplicate Stability" in report
    assert "Gold Answer" in report
    assert "Actual Answer" in report
    assert "Source Order" in report
