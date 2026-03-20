"""Cohere 互換 API を使う軽量な reranker クライアント。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

import httpx


class RerankerConfigurationError(ValueError):
    """reranker の必須設定が不足しているときのエラー。"""


class RerankerTransientError(RuntimeError):
    """一時的な reranker エラー。上位で fallback 可能。"""


Payload = dict[str, Any]


class RerankableChunk(Protocol):
    """リランク可能なチャンクのインターフェース。"""

    text: str
    source_file: str
    chunk_index: int
    payload: Payload


@dataclass
class RerankResult:
    """rerank 結果のインデックスとスコア。"""

    index: int
    relevance_score: float | None = None


@dataclass
class CohereCompatibleRerankerClient:
    """Cohere 互換の `/rerank` API を呼ぶシンプルなクライアント。"""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 8.0
    max_tokens_per_doc: int = 1024
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """必要な設定項目が揃っているか確認する。"""
        missing = [
            name
            for name, value in (
                ("RERANK_BASE_URL", self.base_url),
                ("RERANK_API_KEY", self.api_key),
                ("RERANK_MODEL", self.model),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RerankerConfigurationError(
                f"リランカーの設定が不足しています: {joined}"
            )

    def rerank(
        self,
        query: str,
        chunks: Sequence[RerankableChunk],
        top_n: int,
    ) -> list[RerankResult]:
        """クエリとチャンクのリストを受け取り、関連度順に並べ替える。"""
        if top_n <= 0 or not chunks:
            return []

        payload = {
            "model": self.model,
            "query": query,
            "documents": [self._format_document(chunk) for chunk in chunks],
            "top_n": min(top_n, len(chunks)),
            "max_tokens_per_doc": self.max_tokens_per_doc,
        }

        try:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/rerank",
                json=payload,
                headers=self._build_headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise RerankerTransientError("リランカーへのリクエストがタイムアウトしました。") from exc
        except httpx.RequestError as exc:
            raise RerankerTransientError("リランカーへのリクエストに失敗しました。") from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise RerankerTransientError(
                f"リランカーが一時的に利用不可能です: HTTP {response.status_code}"
            )

        response.raise_for_status()
        return self._parse_results(response.json())

    def _build_headers(self) -> dict[str, str]:
        """リクエストヘッダーを構築する。"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.extra_headers)
        return headers

    def _format_document(self, chunk: RerankableChunk) -> str:
        """チャンクをリランカーに送信するためのテキスト形式にフォーマットする。"""
        payload = chunk.payload or {}
        lines = [
            f"source_file: {chunk.source_file}",
            f"chunk_index: {chunk.chunk_index}",
        ]
        formula_description = payload.get("formula_description")
        if formula_description:
            lines.append(f"formula_description: {formula_description}")
        lines.extend(
            [
                "text: |",
                *[f"  {line}" for line in chunk.text.splitlines() or [""]],
            ]
        )
        return "\n".join(lines)

    def _parse_results(self, payload: Any) -> list[RerankResult]:
        """API レスポンスを解析して結果のリストを返す。"""
        if not isinstance(payload, dict):
            raise ValueError("リランカーのレスポンスは JSON オブジェクトである必要があります。")

        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise ValueError("リランカーのレスポンスに結果リスト（results）が含まれていません。")

        results: list[RerankResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if not isinstance(index, int):
                continue

            score = item.get("relevance_score")
            results.append(
                RerankResult(
                    index=index,
                    relevance_score=float(score) if isinstance(score, (int, float)) else None,
                )
            )

        return results
