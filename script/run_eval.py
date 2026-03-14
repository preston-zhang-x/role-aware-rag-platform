"""
RAG 自動評測スクリプト。

使い方:
    1. FastAPI サーバーを起動:  uvicorn app.main:app --reload
    2. 別ターミナルで実行:      python script/run_eval.py

出力:
    - コンソールに結果を表示
    - docs/week02_baseline.md に保存
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

# ── プロジェクトルートを Python パスに追加 ─────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 定数 ──────────────────────────────────────────────────────
RAG_API_URL = "http://localhost:8000/api/v1/rag/ask"
EVAL_FILE = Path("data/fixtures/eval_questions.json")
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "week02_baseline.md"

# リクエストのタイムアウト（秒）- LLM は遅いので長めに設定
TIMEOUT_SECONDS = 60.0


def load_eval_questions() -> list[dict]:
    """
    評測問題を JSON ファイルから読み込む。
    """
    with open(EVAL_FILE, encoding="utf-8") as f:
        questions = json.load(f)

    print(f"📂 {len(questions)} 件の評測問題を読み込みました")
    return questions


def call_rag_api(question: str, role: str) -> dict:
    """
    RAG API を呼び出して結果を取得する。
    """
    payload = {"question": question, "role": role}

    # httpx.post() は Java の RestTemplate.postForObject() に相当
    response = httpx.post(
        RAG_API_URL,
        json=payload,                      # 自動的に Content-Type: application/json
        timeout=TIMEOUT_SECONDS,
    )

    # ステータスコードチェック（Java の response.getStatusCode().is2xxSuccessful()）
    response.raise_for_status()

    return response.json()


def evaluate_answer(answer: str, expected_keywords: list[str]) -> bool:
    """
    回答に期待キーワードが含まれるか判定する。
    """
    # Python の all() は Java の Stream.allMatch() と同じ
    answer_lower = answer.lower()
    return all(keyword.lower() in answer_lower for keyword in expected_keywords)


def run_eval() -> dict:
    """
    全問題を順番に実行して結果を集計する。
    """
    questions = load_eval_questions()

    results = []      # 各問題の結果を記録
    hit_count = 0     # ヒット数（正解数）
    error_count = 0   # エラー数

    for i, q in enumerate(questions, start=1):
        qid = q["id"]
        question = q["question"]
        expected = q["expected"]
        role = q.get("role", "viewer")  # デフォルトは viewer

        print(f"\n── [{i}/{len(questions)}] Q{qid}: {question}")

        try:
            # RAG API を呼ぶ
            resp = call_rag_api(question, role)
            answer = resp.get("answer", "")
            sources = resp.get("sources", [])

            # キーワード判定
            hit = evaluate_answer(answer, expected)
            if hit:
                hit_count += 1

            status = "HIT" if hit else "MISS"
            print(f"   {status}")
            print(f"   回答（先頭100文字）: {answer[:100]}...")

            results.append({
                "id": qid,
                "question": question,
                "expected": expected,
                "role": role,
                "answer": answer,
                "sources_count": len(sources),
                "hit": hit,
                "error": None,
            })

        except httpx.HTTPStatusError as e:
            print(f"   ⚠️ HTTP エラー: {e.response.status_code}")
            error_count += 1
            results.append({
                "id": qid,
                "question": question,
                "expected": expected,
                "role": role,
                "answer": "",
                "sources_count": 0,
                "hit": False,
                "error": f"HTTP {e.response.status_code}",
            })

        except httpx.ConnectError:
            print("   ❌ サーバーに接続できません。uvicorn が起動していますか？")
            print("   起動コマンド: uvicorn app.main:app --reload")
            sys.exit(1)

        except Exception as e:
            print(f"   ⚠️ エラー: {e}")
            error_count += 1
            results.append({
                "id": qid,
                "question": question,
                "expected": expected,
                "role": role,
                "answer": "",
                "sources_count": 0,
                "hit": False,
                "error": str(e),
            })

    # ── 集計 ──
    total = len(questions)
    accuracy = (hit_count / total * 100) if total > 0 else 0.0

    summary = {
        "total": total,
        "hit": hit_count,
        "miss": total - hit_count - error_count,
        "error": error_count,
        "accuracy": accuracy,
        "results": results,
    }

    print(f"\n{'=' * 60}")
    print(f"評測結果: {hit_count}/{total} = {accuracy:.1f}%")
    print(f"   HIT: {hit_count}  MISS: {total - hit_count - error_count}  ERROR: {error_count}")

    return summary


def generate_report(summary: dict) -> str:
    """
    Markdown 形式のレポートを生成する。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── ヘッダー ──
    lines = [
        "# Week02 Baseline 評測レポート",
        "",
        f"**実行日時**: {now}",
        f"**API エンドポイント**: `{RAG_API_URL}`",
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
        "## 詳細結果",
        "",
        "| ID | Question | Role | Hit | Sources | Error |",
        "|----|----------|------|-----|---------|-------|",
    ]

    # ── 各問題の行を追加 ──
    for r in summary["results"]:
        hit_mark = "HIT" if r["hit"] else "MISS"
        error_text = r["error"] or "-"
        # 質問文が長すぎる場合は truncate
        q_short = r["question"][:30] + "..." if len(r["question"]) > 30 else r["question"]
        lines.append(
            f"| {r['id']} | {q_short} | {r['role']} | {hit_mark} | {r['sources_count']} | {error_text} |"
        )

    # ── MISS した問題の詳細 ──
    miss_results = [r for r in summary["results"] if not r["hit"] and not r["error"]]
    if miss_results:
        lines.append("")
        lines.append("## MISS 詳細分析")
        lines.append("")
        for r in miss_results:
            lines.append(f"### Q{r['id']}: {r['question']}")
            lines.append(f"- **期待キーワード**: {', '.join(r['expected'])}")
            lines.append(f"- **実際の回答**: {r['answer'][:200]}...")
            lines.append("")

    # ── フッター ──
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by `script/run_eval.py` at {now}*")

    return "\n".join(lines)


def main():
    """メインエントリーポイント。Java の public static void main に相当。"""
    print("RAG 評測を開始します...")
    print(f"   評測ファイル: {EVAL_FILE}")
    print(f"   API: {RAG_API_URL}")
    print("=" * 60)

    # 1. 評測実行
    summary = run_eval()

    # 2. レポート生成
    report = generate_report(summary)

    # 3. ファイル保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # mkdir -p と同じ
    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(f"\n📝 レポートを保存しました: {OUTPUT_FILE}")

    # 4. 正解率が低い場合の警告
    if summary["accuracy"] < 50:
        print("\n  正解率が 50% 未満です。以下を確認してください：")
        print("   - ドキュメントが正しく Qdrant に ingest されているか")
        print("   - eval_questions.json のキーワードが適切か")
        print("   - ロールのフィルタリングが問題ないか")


if __name__ == "__main__":
    main()
