"""
RAG 自動評測スクリプト。

使い方:
    1. FastAPI サーバーを起動:  uvicorn app.main:app --reload
    2. 環境変数を設定:
         - EVAL_ADMIN_USERNAME
         - EVAL_ADMIN_PASSWORD
    3. 別ターミナルで実行:      python script/run_eval.py

出力:
    - コンソールに結果を表示
    - docs/report_baseline.md に保存
"""

import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# ── プロジェクトルートを Python パスに追加 ─────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 定数 ──────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000/api/v1"
AUTH_API_URL = f"{API_BASE_URL}/auth/login"
RAG_API_URL = f"{API_BASE_URL}/rag/ask"
EVAL_FILE = Path("data/fixtures/eval_questions.json")
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "report_baseline.md"
TIMEOUT_SECONDS = 60.0
EXECUTION_MODE = "admin-only evaluation"
EXECUTED_AS_ROLE = "admin"
NOT_FOUND_PATTERNS = (
    "該当する情報が見つかりません",
    "見つかりません",
)


def load_eval_questions() -> list[dict[str, Any]]:
    """評測問題を JSON ファイルから読み込む。"""
    with open(EVAL_FILE, encoding="utf-8") as f:
        questions = json.load(f)

    print(f"📂 {len(questions)} 件の評測問題を読み込みました")
    return questions


def get_admin_credentials() -> tuple[str, str]:
    """環境変数から admin 評測用の資格情報を取得する。"""
    username = os.getenv("EVAL_ADMIN_USERNAME")
    password = os.getenv("EVAL_ADMIN_PASSWORD")

    missing_vars = [
        env_var
        for env_var, value in (
            ("EVAL_ADMIN_USERNAME", username),
            ("EVAL_ADMIN_PASSWORD", password),
        )
        if not value
    ]
    if missing_vars:
        joined = ", ".join(missing_vars)
        raise RuntimeError(
            f"Missing required environment variables: {joined}. "
            "Set them before running script/run_eval.py."
        )

    return username, password


def extract_error_detail(response: httpx.Response) -> str:
    """HTTP エラー詳細を人が読める文字列として取り出す。"""
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
    return json.dumps(payload, ensure_ascii=False)


def login_as_admin(username: str, password: str) -> str:
    """admin ユーザーでログインし Bearer token を取得する。"""
    try:
        response = httpx.post(
            AUTH_API_URL,
            data={"username": username, "password": password},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "認証 API に接続できません。uvicorn が起動しているか確認してください。 "
            "起動コマンド: uvicorn app.main:app --reload"
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = extract_error_detail(exc.response)
        raise RuntimeError(
            f"Admin login failed with HTTP {exc.response.status_code}: {detail}"
        ) from exc

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Admin login succeeded but access_token is missing.")

    return access_token


def call_rag_api(question: str, access_token: str) -> dict[str, Any]:
    """Bearer token 付きで RAG API を呼び出して結果を取得する。"""
    try:
        response = httpx.post(
            RAG_API_URL,
            json={"question": question},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "RAG API に接続できません。uvicorn が起動しているか確認してください。 "
            "起動コマンド: uvicorn app.main:app --reload"
        ) from exc

    response.raise_for_status()
    return response.json()


def normalize_text(text: str) -> str:
    """比較用に文字種と空白を正規化する。"""
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def evaluate_answer(answer: str, expected_keywords: list[str]) -> tuple[bool, list[str]]:
    """回答に期待キーワードが含まれるか判定し、不足分も返す。"""
    normalized_answer = normalize_text(answer)
    missing_keywords = [
        keyword
        for keyword in expected_keywords
        if normalize_text(keyword) not in normalized_answer
    ]
    return len(missing_keywords) == 0, missing_keywords


def determine_miss_reason(answer: str, sources_count: int, hit: bool) -> str | None:
    """非 HIT の一次原因を固定ルールで分類する。"""
    if hit:
        return None
    if sources_count == 0:
        return "no_sources"

    normalized_answer = normalize_text(answer)
    if any(normalize_text(pattern) in normalized_answer for pattern in NOT_FOUND_PATTERNS):
        return "not_found_answer"

    return "keyword_mismatch"


def truncate_text(text: str, limit: int) -> str:
    """レポート表示用にテキストを短く整える。"""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_requested_role_breakdown(
    results: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Requested Role ごとの HIT/MISS/ERROR を集計する。"""
    breakdown: dict[str, dict[str, int]] = {}
    for result in results:
        requested_role = result["requested_role"]
        role_summary = breakdown.setdefault(
            requested_role,
            {"total": 0, "hit": 0, "miss": 0, "error": 0},
        )
        role_summary["total"] += 1
        if result["error"]:
            role_summary["error"] += 1
        elif result["hit"]:
            role_summary["hit"] += 1
        else:
            role_summary["miss"] += 1
    return breakdown


def build_miss_reason_breakdown(results: list[dict[str, Any]]) -> dict[str, int]:
    """miss_reason ごとの件数を集計する。"""
    counter = Counter(
        result["miss_reason"]
        for result in results
        if not result["hit"] and result["miss_reason"]
    )
    return dict(counter)


def run_eval() -> dict[str, Any]:
    """全問題を順番に実行して結果を集計する。"""
    username, password = get_admin_credentials()
    access_token = login_as_admin(username, password)
    print("🔐 Admin login succeeded. Running evaluation in admin-only mode.")

    questions = load_eval_questions()

    results: list[dict[str, Any]] = []
    hit_count = 0
    error_count = 0

    for i, q in enumerate(questions, start=1):
        qid = q["id"]
        question = q["question"]
        expected = q["expected"]
        requested_role = q.get("role", "viewer")

        print(f"\n── [{i}/{len(questions)}] Q{qid}: {question}")
        print(f"   Requested Role: {requested_role} / Executed As: {EXECUTED_AS_ROLE}")

        try:
            resp = call_rag_api(question, access_token)
            answer = resp.get("answer", "")
            sources = resp.get("sources", [])
            hit, missing_keywords = evaluate_answer(answer, expected)
            miss_reason = determine_miss_reason(answer, len(sources), hit)
            if hit:
                hit_count += 1

            status = "HIT" if hit else "MISS"
            print(f"   {status} ({miss_reason or '-'})")
            print(f"   回答（先頭100文字）: {truncate_text(answer, 100)}")

            results.append(
                {
                    "id": qid,
                    "question": question,
                    "expected": expected,
                    "requested_role": requested_role,
                    "executed_as": EXECUTED_AS_ROLE,
                    "answer": answer,
                    "sources_count": len(sources),
                    "first_source_file": (
                        sources[0].get("source_file") if sources else None
                    ),
                    "hit": hit,
                    "missing_keywords": missing_keywords,
                    "miss_reason": miss_reason,
                    "error": None,
                }
            )

        except httpx.HTTPStatusError as e:
            error_count += 1
            detail = extract_error_detail(e.response)
            error_text = f"HTTP {e.response.status_code}"
            if detail:
                error_text += f": {detail}"

            print(f"   ⚠️ HTTP エラー: {error_text}")
            results.append(
                {
                    "id": qid,
                    "question": question,
                    "expected": expected,
                    "requested_role": requested_role,
                    "executed_as": EXECUTED_AS_ROLE,
                    "answer": "",
                    "sources_count": 0,
                    "first_source_file": None,
                    "hit": False,
                    "missing_keywords": expected,
                    "miss_reason": "http_error",
                    "error": error_text,
                }
            )

        except Exception as e:
            error_count += 1
            print(f"   ⚠️ エラー: {e}")
            results.append(
                {
                    "id": qid,
                    "question": question,
                    "expected": expected,
                    "requested_role": requested_role,
                    "executed_as": EXECUTED_AS_ROLE,
                    "answer": "",
                    "sources_count": 0,
                    "first_source_file": None,
                    "hit": False,
                    "missing_keywords": expected,
                    "miss_reason": "unexpected_error",
                    "error": str(e),
                }
            )

    total = len(questions)
    accuracy = (hit_count / total * 100) if total > 0 else 0.0

    summary = {
        "total": total,
        "hit": hit_count,
        "miss": total - hit_count - error_count,
        "error": error_count,
        "accuracy": accuracy,
        "execution_mode": EXECUTION_MODE,
        "executed_as": EXECUTED_AS_ROLE,
        "results": results,
        "requested_role_breakdown": build_requested_role_breakdown(results),
        "miss_reason_breakdown": build_miss_reason_breakdown(results),
    }

    print(f"\n{'=' * 60}")
    print(f"評測結果: {hit_count}/{total} = {accuracy:.1f}%")
    print(f"   HIT: {hit_count}  MISS: {summary['miss']}  ERROR: {error_count}")
    print(f"   実行モード: {EXECUTION_MODE}")

    return summary


def generate_report(summary: dict[str, Any]) -> str:
    """Markdown 形式のレポートを生成する。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Week02 Baseline 評測レポート",
        "",
        f"**実行日時**: {now}",
        f"**実行モード**: `{summary['execution_mode']}`",
        f"**API エンドポイント**: `{RAG_API_URL}`",
        f"**認証エンドポイント**: `{AUTH_API_URL}`",
        f"**実行権限**: `{summary['executed_as']}`",
        "",
        "## サマリー",
        "",
        "| 指標 | 値 |",
        "|------|-----|",
        f"| 総問題数 | {summary['total']} |",
        f"| HIT（正解） | {summary['hit']} |",
        f"| MISS（不正解） | {summary['miss']} |",
        f"| ERROR | {summary['error']} |",
        f"| **正解率** | **{summary['accuracy']:.1f}%** |",
        "",
        "## Requested Role 別集計",
        "",
        "| Requested Role | Total | HIT | MISS | ERROR |",
        "|----------------|-------|-----|------|-------|",
    ]

    for role, role_summary in summary["requested_role_breakdown"].items():
        lines.append(
            "| "
            f"{role} | {role_summary['total']} | {role_summary['hit']} | "
            f"{role_summary['miss']} | {role_summary['error']} |"
        )

    lines.extend(
        [
            "",
            "## Miss Reason 別集計",
            "",
            "| Miss Reason | Count |",
            "|-------------|-------|",
        ]
    )

    miss_reason_breakdown = summary["miss_reason_breakdown"]
    if miss_reason_breakdown:
        for reason, count in miss_reason_breakdown.items():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| - | 0 |")

    lines.extend(
        [
            "",
            "## 詳細結果",
            "",
            "| ID | Question | Requested Role | Executed As | Hit | Sources | Miss Reason | Error |",
            "|----|----------|----------------|-------------|-----|---------|-------------|-------|",
        ]
    )

    for result in summary["results"]:
        hit_mark = "HIT" if result["hit"] else "MISS"
        error_text = result["error"] or "-"
        miss_reason = result["miss_reason"] or "-"
        q_short = truncate_text(result["question"], 30)
        lines.append(
            "| "
            f"{result['id']} | {q_short} | {result['requested_role']} | "
            f"{result['executed_as']} | {hit_mark} | {result['sources_count']} | "
            f"{miss_reason} | {error_text} |"
        )

    non_hit_results = [result for result in summary["results"] if not result["hit"]]
    if non_hit_results:
        lines.extend(["", "## 非 HIT 詳細分析", ""])
        for result in non_hit_results:
            lines.append(f"### Q{result['id']}: {result['question']}")
            lines.append(f"- **Requested Role**: {result['requested_role']}")
            lines.append(f"- **Executed As**: {result['executed_as']}")
            lines.append(f"- **Miss Reason**: {result['miss_reason'] or '-'}")
            lines.append(f"- **期待キーワード**: {', '.join(result['expected'])}")
            lines.append(
                "- **不足キーワード**: "
                + (
                    ", ".join(result["missing_keywords"])
                    if result["missing_keywords"]
                    else "-"
                )
            )
            lines.append(
                f"- **先頭 Source**: {result['first_source_file'] or '-'}"
            )
            if result["error"]:
                lines.append(f"- **Error**: {result['error']}")
            lines.append(
                f"- **実際の回答**: {truncate_text(result['answer'], 200) or '-'}"
            )
            lines.append("")

    lines.extend(
        [
            "---",
            f"*Generated by `script/run_eval.py` at {now}*",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """メインエントリーポイント。"""
    print("RAG 評測を開始します...")
    print(f"   評測ファイル: {EVAL_FILE}")
    print(f"   認証 API: {AUTH_API_URL}")
    print(f"   RAG API: {RAG_API_URL}")
    print(f"   実行モード: {EXECUTION_MODE}")
    print("=" * 60)

    try:
        summary = run_eval()
    except RuntimeError as exc:
        print(f"\n❌ {exc}")
        sys.exit(1)

    report = generate_report(summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(f"\n📝 レポートを保存しました: {OUTPUT_FILE}")

    if summary["accuracy"] < 50:
        print("\n  正解率が 50% 未満です。以下を確認してください：")
        print("   - ドキュメントが正しく Qdrant に ingest されているか")
        print("   - eval_questions.json のキーワードが適切か")
        print("   - 回答失敗要因（Miss Reason）の偏りがないか")


if __name__ == "__main__":
    main()
