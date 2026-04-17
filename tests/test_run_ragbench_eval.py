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
    assert "Gold Answer" in report
    assert "Actual Answer" in report
