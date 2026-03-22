from pathlib import Path

import httpx
import pytest

from script import run_eval


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


def test_run_eval_requires_admin_credentials_before_requests(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EVAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("EVAL_ADMIN_PASSWORD", raising=False)

    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        return make_response(run_eval.AUTH_API_URL)

    monkeypatch.setattr(run_eval.httpx, "post", fake_post)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        run_eval.run_eval()

    assert called is False


def test_run_eval_logs_in_once_and_reuses_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EVAL_ADMIN_USERNAME", "admin1")
    monkeypatch.setenv("EVAL_ADMIN_PASSWORD", "password123")
    monkeypatch.setattr(
        run_eval,
        "load_eval_questions",
        lambda: [
            {"id": 1, "question": "Q1", "expected": ["alpha"], "role": "viewer"},
            {"id": 2, "question": "Q2", "expected": ["beta"], "role": "admin"},
        ],
    )

    calls: list[tuple[str, dict]] = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        if url == run_eval.AUTH_API_URL:
            assert kwargs["data"] == {
                "username": "admin1",
                "password": "password123",
            }
            return make_response(
                url,
                json_data={
                    "access_token": "test-token",
                    "token_type": "bearer",
                    "role": "admin",
                },
            )

        assert url == run_eval.RAG_API_URL
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"
        assert kwargs["json"] in ({"question": "Q1"}, {"question": "Q2"})
        answer = "alpha" if kwargs["json"]["question"] == "Q1" else "beta"
        return make_response(
            url,
            json_data={
                "answer": answer,
                "sources": [
                    {
                        "text": "matched source",
                        "source_file": "docs/spec.xlsx",
                        "score": 0.9,
                        "chunk_index": 0,
                    }
                ],
            },
        )

    monkeypatch.setattr(run_eval.httpx, "post", fake_post)

    summary = run_eval.run_eval()

    auth_calls = [url for url, _ in calls if url == run_eval.AUTH_API_URL]
    rag_calls = [url for url, _ in calls if url == run_eval.RAG_API_URL]

    assert len(auth_calls) == 1
    assert len(rag_calls) == 2
    assert summary["hit"] == 2
    assert all(result["executed_as"] == "admin" for result in summary["results"])
    assert summary["requested_role_breakdown"]["viewer"]["total"] == 1
    assert summary["requested_role_breakdown"]["admin"]["total"] == 1


def test_evaluate_answer_normalizes_text_and_reports_missing_keywords():
    hit, missing = run_eval.evaluate_answer(
        "Ｔｏｋｅｎ　Ｔｙｐｅ is token_type",
        ["token type", "TOKEN_TYPE"],
    )
    assert hit is True
    assert missing == []

    hit, missing = run_eval.evaluate_answer("alpha only", ["alpha", "beta"])
    assert hit is False
    assert missing == ["beta"]


def test_determine_miss_reason_classifies_expected_categories():
    assert run_eval.determine_miss_reason("whatever", 0, False) == "no_sources"
    assert (
        run_eval.determine_miss_reason(
            "ドキュメントに該当する情報が見つかりませんでした。",
            2,
            False,
        )
        == "not_found_answer"
    )
    assert run_eval.determine_miss_reason("partial answer", 2, False) == "keyword_mismatch"
    assert run_eval.determine_miss_reason("full answer", 2, True) is None


def test_generate_report_includes_new_diagnostic_sections():
    summary = {
        "total": 2,
        "hit": 1,
        "miss": 1,
        "error": 0,
        "accuracy": 50.0,
        "execution_mode": "admin-only evaluation",
        "executed_as": "admin",
        "requested_role_breakdown": {
            "admin": {"total": 1, "hit": 1, "miss": 0, "error": 0},
            "viewer": {"total": 1, "hit": 0, "miss": 1, "error": 0},
        },
        "miss_reason_breakdown": {"keyword_mismatch": 1},
        "results": [
            {
                "id": 1,
                "question": "What is the title?",
                "expected": ["Role Aware RAG Platform"],
                "requested_role": "admin",
                "executed_as": "admin",
                "answer": "Role Aware RAG Platform",
                "sources_count": 1,
                "first_source_file": "docs/spec.xlsx",
                "hit": True,
                "missing_keywords": [],
                "miss_reason": None,
                "error": None,
            },
            {
                "id": 2,
                "question": "CFG-002 のコード既定値は何ですか？",
                "expected": ["HS256"],
                "requested_role": "viewer",
                "executed_as": "admin",
                "answer": "設定値は HMAC です。",
                "sources_count": 1,
                "first_source_file": "docs/spec.xlsx",
                "hit": False,
                "missing_keywords": ["HS256"],
                "miss_reason": "keyword_mismatch",
                "error": None,
            },
        ],
    }

    report = run_eval.generate_report(summary)

    assert "admin-only evaluation" in report
    assert "Requested Role" in report
    assert "Executed As" in report
    assert "Miss Reason" in report
    assert "keyword_mismatch" in report
    assert "docs/spec.xlsx" in report
    assert "不足キーワード" in report


def test_output_file_points_to_report_baseline():
    assert run_eval.OUTPUT_FILE == Path("docs") / "report_baseline.md"
