"""RAG の検索・生成パイプライン本体。"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import httpx
import openai
from openai import OpenAI
from qdrant_client.http.models import FieldCondition, Filter, MatchAny

from app.clients.qdrant_client import get_qdrant_client
from app.core.config import get_openai_settings, get_retrieval_settings
from app.core.model_provider import (
    build_auth_headers,
    build_chat_extra_body,
    build_ollama_native_chat_url,
    build_ollama_native_options,
    is_ollama_base_url,
)
from app.services.bm25_service import BM25Hit, get_cached_bm25_service
from app.services.hybrid_retriever import reciprocal_rank_fusion
from app.services.reranker_service import (
    CohereCompatibleRerankerClient,
    RerankerTransientError,
)

logger = logging.getLogger(__name__)
JAPANESE_NOT_FOUND_ANSWER = "ドキュメントに該当する情報が見つかりませんでした。"
ENGLISH_NOT_FOUND_ANSWER = "No relevant information was found in the documents."
JAPANESE_FALLBACK_ANSWER = (
    "現在サービスが混雑しています。しばらくしてからもう一度お試しください。"
)
ENGLISH_FALLBACK_ANSWER = "The service is currently busy. Please try again later."
# Backward-compatible aliases kept for older tests/import sites.
NOT_FOUND_ANSWER = JAPANESE_NOT_FOUND_ANSWER
FALLBACK_ANSWER = JAPANESE_FALLBACK_ANSWER
LLM_TIMEOUT_SECONDS = 30.0
DEFAULT_COLLECTION = "documents"
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATE_TOP_K = 20
DEFAULT_RERANK_CANDIDATE_TOP_K = 40
DEFAULT_RERANK_RETURN_TOP_N = 15
VALID_RETRIEVAL_MODES = {"vector", "bm25", "hybrid", "hybrid_rerank"}
Payload = dict[str, Any]
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
_CITATION_RE = re.compile(r"\[Reference \d+\]")
_NON_ENGLISH_SCRIPT_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]|[ãáàâçéêíóôõúñ¿¡]")
_NON_ENGLISH_HINTS = (
    " para ",
    " conforme ",
    " instruções ",
    " referências ",
    " configuraciones ",
    " configurações ",
    " transmisión ",
    " áudio ",
)

SYSTEM_PROMPT = (
    "あなたは、提供された参照情報を用いて質問に回答するリトリーバルアシスタントです。\n"
    "回答は必ず参照情報の内容のみに基づいて行ってください。\n"
    "回答はユーザーの質問と同じ言語で行ってください。\n"
    "ユーザーの質問が英語の場合は、必ず英語のみで回答し、他の言語に切り替えないでください。\n"
    "参照情報に回答が含まれていない場合は、その旨をユーザーの質問と同じ言語で明確に伝えてください。\n"
    "回答は簡潔にし、参照情報に含まれる場合は正確なメニュー経路や操作手順を必ず含めてください。\n"
    "必ず参照情報に表示されている正確なソースラベル（例：[Reference 1]）を用いて出典を明記してください。"
)


# ── 結果データクラス ─────────────────────────────────────────
@dataclass
class SourceChunk:
    """検索でヒットした1つのチャンクの情報。"""

    text: str
    source_file: str
    score: float
    chunk_index: int = 0
    payload: Payload = field(default_factory=dict)
    fusion_score: float | None = None
    rerank_score: float | None = None


@dataclass
class RagResult:
    """RAG の最終結果。"""

    answer: str
    sources: list[SourceChunk] = field(default_factory=list)
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# ── RAG Service 本体 ────────────────────────────────────────
class RagService:
    """RAG のコアロジックを実装するサービスクラス。"""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        top_k: int | None = None,
        qdrant_wrapper=None,
        retrieval_mode: str | None = None,
        reranker_client: CohereCompatibleRerankerClient | None = None,
        bm25_provider: Callable[..., Any] | None = None,
    ) -> None:
        self.openai_settings = deepcopy(get_openai_settings())
        self.retrieval_settings = deepcopy(get_retrieval_settings())
        self.collection_name = collection_name
        self.top_k = self.retrieval_settings.top_k if top_k is None else top_k
        if self.top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        self.retrieval_mode = self.retrieval_settings.retrieval_mode
        if retrieval_mode is not None:
            self.retrieval_mode = retrieval_mode
        if self.retrieval_mode not in VALID_RETRIEVAL_MODES:
            raise ValueError(f"unsupported retrieval_mode: {self.retrieval_mode}")

        self.score_threshold = self.retrieval_settings.score_threshold
        self.rerank_score_threshold = getattr(
            self.retrieval_settings,
            "rerank_score_threshold",
            None,
        )
        self.rerank_max_tokens_per_doc = getattr(
            self.retrieval_settings,
            "rerank_max_tokens_per_doc",
            1024,
        )
        self.qdrant_wrapper = qdrant_wrapper or get_qdrant_client()
        self.bm25_provider = bm25_provider or get_cached_bm25_service
        self.reranker_client = reranker_client
        # OpenAI クライアント初期化（Embedding + Chat 両方で使う）
        self.openai_client = OpenAI(
            api_key=self.openai_settings.openai_api_key,
            base_url=self.openai_settings.openai_base_url,
        )
        if self.retrieval_mode == "hybrid_rerank" and self.reranker_client is None:
            self.reranker_client = CohereCompatibleRerankerClient(
                base_url=self.retrieval_settings.rerank_base_url or "",
                api_key=self.retrieval_settings.rerank_api_key or "",
                model=self.retrieval_settings.rerank_model or "",
                timeout_seconds=self.retrieval_settings.rerank_timeout_seconds,
            )

    def ask(self, question: str, user_roles: list[str]) -> RagResult:
        """
        RAG のメインメソッド。質問を受け取り、回答を返す。
        """
        start = time.perf_counter()
        sources = self._retrieve_sources(question, user_roles)
        if not sources:
            return RagResult(
                answer=self._build_not_found_answer(question),
                sources=[],
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        # 4. Prompt を組み立てて LLM に投げる（Generation）
        (
            answer,
            _generation_latency_ms,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ) = self._generate(question, sources)
        return RagResult(
            answer=answer,
            sources=sources,
            latency_ms=(time.perf_counter() - start) * 1000,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    # ── Private メソッド ─────────────────────────────────────
    def _embed_query(self, text: str) -> list[float]:
        """
        テキストを Embedding ベクトルに変換する。
        """
        response = self.openai_client.embeddings.create(
            model=self.openai_settings.embedding_model,
            input=text,
            dimensions=self.openai_settings.embedding_dimensions,
        )
        return response.data[0].embedding

    def _retrieve_sources(
        self,
        question: str,
        user_roles: list[str],
    ) -> list[SourceChunk]:
        """質問の内容とユーザー権限に基づいてソースを取得する。"""
        if self.retrieval_mode == "vector":
            sources = self._search(
                self._embed_query(question),
                user_roles,
                limit=self.top_k,
            )
            return self._filter_by_score(sources)

        if self.retrieval_mode == "bm25":
            sources = self._search_bm25(question, user_roles, limit=self.top_k)
            return self._filter_by_score(sources)

        if self.retrieval_mode == "hybrid":
            hybrid_sources = self._search_hybrid(
                question,
                user_roles,
                candidate_limit=self.candidate_top_k,
            )
            return self._filter_by_score(hybrid_sources[: self.top_k])

        hybrid_sources = self._search_hybrid(
            question,
            user_roles,
            candidate_limit=self.rerank_candidate_top_k,
        )
        return self._finalize_reranked_sources(question, hybrid_sources)

    @property
    def candidate_top_k(self) -> int:
        return max(DEFAULT_CANDIDATE_TOP_K, self.top_k * 4)

    @property
    def rerank_candidate_top_k(self) -> int:
        configured = getattr(
            self.retrieval_settings,
            "rerank_candidate_top_k",
            None,
        )
        if configured is not None:
            return max(configured, self.top_k)
        return max(DEFAULT_RERANK_CANDIDATE_TOP_K, self.top_k * 8)

    @property
    def rerank_return_top_n(self) -> int:
        configured = getattr(
            self.retrieval_settings,
            "rerank_return_top_n",
            None,
        )
        value = (
            configured
            if configured is not None
            else max(
                DEFAULT_RERANK_RETURN_TOP_N,
                self.top_k * 3,
            )
        )
        return min(max(value, self.top_k), self.rerank_candidate_top_k)

    def _search(
        self,
        query_vector: list[float],
        user_roles: list[str],
        *,
        limit: int | None = None,
    ) -> list[SourceChunk]:
        """
        Qdrant からユーザーの権限に合った類似チャンクを検索する。
        """
        query_filter = self._build_role_filter(user_roles)
        search_limit = self.top_k if limit is None else limit

        # Qdrant で検索実行
        results = self.qdrant_wrapper.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=search_limit,
            with_payload=True,
        )

        # 検索結果をSourceChunkに変換
        return [self._point_to_source_chunk(point) for point in results.points]

    def _search_bm25(
        self,
        question: str,
        user_roles: list[str],
        *,
        limit: int,
    ) -> list[SourceChunk]:
        """BM25 検索を実行する。"""
        hits = self._search_bm25_hits(question, user_roles, limit=limit)
        return [self._bm25_hit_to_source_chunk(hit) for hit in hits]

    def _search_bm25_hits(
        self,
        question: str,
        user_roles: list[str],
        *,
        limit: int,
    ) -> list[BM25Hit]:
        """BM25 検索を実行し、Raw Hit を返す。"""
        bm25_service = self.bm25_provider(
            collection_name=self.collection_name,
            user_roles=user_roles,
            qdrant_wrapper=self.qdrant_wrapper,
        )
        return bm25_service.search(question, top_k=limit)

    def _search_hybrid(
        self,
        question: str,
        user_roles: list[str],
        *,
        candidate_limit: int,
    ) -> list[SourceChunk]:
        """ベクトル検索と BM25 検索を組み合わせたハイブリッド検索を実行する。"""
        query_vector = self._embed_query(question)
        vector_hits = self._search(query_vector, user_roles, limit=candidate_limit)
        bm25_hits = self._search_bm25_hits(question, user_roles, limit=candidate_limit)
        fused_hits = reciprocal_rank_fusion(
            vector_hits,
            bm25_hits,
            top_k=candidate_limit,
        )
        return [
            SourceChunk(
                text=hit.text,
                source_file=hit.source_file,
                score=hit.rrf_score,
                chunk_index=hit.chunk_index,
                payload=dict(hit.payload),
                fusion_score=hit.rrf_score,
            )
            for hit in fused_hits
        ]

    def _finalize_reranked_sources(
        self,
        question: str,
        hybrid_sources: list[SourceChunk],
    ) -> list[SourceChunk]:
        reranked_sources = self._rerank_sources(question, hybrid_sources)
        if self.rerank_score_threshold is not None:
            reranked_sources = self._filter_by_rerank_score(reranked_sources)
        return reranked_sources[: self.top_k]

    def _rerank_sources(
        self,
        question: str,
        sources: list[SourceChunk],
    ) -> list[SourceChunk]:
        """取得したソースをリランカーで再ランク付けする。"""
        if not sources or self.reranker_client is None:
            return sources[: self.top_k]

        try:
            reranked = self.reranker_client.rerank(
                question,
                sources[: self.rerank_candidate_top_k],
                top_n=self.rerank_return_top_n,
                max_tokens_per_doc=self.rerank_max_tokens_per_doc,
            )
        except RerankerTransientError:
            return sources[: self.top_k]

        ordered: list[SourceChunk] = []
        seen_indexes: set[int] = set()
        for item in reranked:
            if item.index in seen_indexes:
                continue
            if 0 <= item.index < len(sources):
                ordered.append(
                    self._with_rerank_score(
                        sources[item.index],
                        item.relevance_score,
                    )
                )
                seen_indexes.add(item.index)

        if not ordered:
            return sources[: self.top_k]

        target_count = min(self.rerank_return_top_n, len(sources))
        for index, source in enumerate(sources):
            if len(ordered) >= target_count:
                break
            if index in seen_indexes:
                continue
            ordered.append(source)
            seen_indexes.add(index)

        return ordered[:target_count]

    def _with_rerank_score(
        self,
        source: SourceChunk,
        rerank_score: float | None,
    ) -> SourceChunk:
        fusion_score = (
            source.fusion_score if source.fusion_score is not None else source.score
        )
        effective_score = fusion_score if rerank_score is None else rerank_score
        return SourceChunk(
            text=source.text,
            source_file=source.source_file,
            score=effective_score,
            chunk_index=source.chunk_index,
            payload=dict(source.payload),
            fusion_score=fusion_score,
            rerank_score=rerank_score,
        )

    def _filter_by_score(self, sources: list[SourceChunk]) -> list[SourceChunk]:
        """スコアが閾値未満のチャンクを除外する。"""
        if self.score_threshold <= 0:
            return sources
        filtered = [s for s in sources if s.score >= self.score_threshold]
        dropped = len(sources) - len(filtered)
        if dropped > 0:
            logger.info(
                "score_threshold=%s により %d 件のチャンクを除外しました",
                self.score_threshold,
                dropped,
            )
        return filtered

    def _filter_by_rerank_score(self, sources: list[SourceChunk]) -> list[SourceChunk]:
        """rerank スコアが閾値未満のチャンクを除外する。"""
        if self.rerank_score_threshold is None:
            return sources
        if all(source.rerank_score is None for source in sources):
            return sources
        filtered = [
            source
            for source in sources
            if source.rerank_score is not None
            and source.rerank_score >= self.rerank_score_threshold
        ]
        dropped = len(sources) - len(filtered)
        if dropped > 0:
            logger.info(
                "rerank_score_threshold=%s により %d 件のチャンクを除外しました",
                self.rerank_score_threshold,
                dropped,
            )
        return filtered

    def _build_role_filter(self, user_roles: list[str]) -> Filter:
        """ユーザーの権限に基づいたフィルターを構築する。"""
        return Filter(
            must=[
                FieldCondition(
                    key="allowed_roles",
                    match=MatchAny(any=user_roles),
                )
            ]
        )

    def _point_to_source_chunk(self, point: Any) -> SourceChunk:
        """Qdrant の Point を SourceChunk に変換する。"""
        payload = point.payload or {}
        text = self._extract_text(payload)
        return SourceChunk(
            text=text,
            source_file=payload.get("source_file", "unknown"),
            score=float(point.score),
            chunk_index=payload.get("chunk_index", 0),
            payload=dict(payload),
            fusion_score=float(point.score),
        )

    def _bm25_hit_to_source_chunk(self, hit: BM25Hit) -> SourceChunk:
        """BM25Hit を SourceChunk に変換する。"""
        return SourceChunk(
            text=hit.text,
            source_file=hit.source_file,
            score=hit.score,
            chunk_index=hit.chunk_index,
            payload=dict(hit.payload),
            fusion_score=hit.score,
        )

    def _extract_text(self, payload: dict) -> str:
        """
        Qdrant の payload からテキストを取り出す。
        """
        node_content = payload.get("_node_content")
        if node_content is None:
            return str(payload.get("text", ""))

        if isinstance(node_content, dict):
            return str(node_content.get("text", ""))

        if isinstance(node_content, str):
            try:
                parsed = json.loads(node_content)
            except (json.JSONDecodeError, TypeError):
                return str(node_content)

            if isinstance(parsed, dict):
                return str(parsed.get("text", ""))
            return str(parsed)

        return str(node_content)

    def _generate(
        self, question: str, sources: list[SourceChunk]
    ) -> tuple[str, float, int, int, int]:
        """
        検索で得たチャンクを元に LLM で回答を生成する。
        Returns: (answer, latency_ms, prompt_tokens, completion_tokens, total_tokens)
        """

        messages = self._build_generation_messages(question, sources)
        result = self._generate_once(question, messages)
        if self._needs_generation_repair(question, result[0], sources):
            repair_messages = self._build_repair_messages(
                question,
                sources,
                result[0],
            )
            repaired = self._generate_once(question, repair_messages)
            if repaired[0].strip():
                return repaired
        return result

    def _generate_once(
        self,
        question: str,
        messages: list[dict[str, str]],
    ) -> tuple[str, float, int, int, int]:
        """1 回分の生成を実行し、必要に応じて fallback を返す。"""

        # LLM に投げる（Chat Completion API）— タイムアウト＆エラーハンドリング付き
        try:
            if self._should_use_ollama_native_chat():
                try:
                    return self._generate_with_ollama_native(messages)
                except (httpx.HTTPError, ValueError):
                    logger.warning(
                        "Ollama native chat への切り替えに失敗したため、"
                        "OpenAI-compatible API にフォールバックします",
                        exc_info=True,
                    )

            return self._generate_with_openai(messages)
        except httpx.TimeoutException:
            logger.warning(
                "Ollama native chat がタイムアウトしました (質問: %.50s...)",
                question,
            )
            return (self._build_fallback_answer(question), 0.0, 0, 0, 0)
        except httpx.RequestError:
            logger.warning(
                "Ollama native chat への接続に失敗しました (質問: %.50s...)",
                question,
            )
            return (self._build_fallback_answer(question), 0.0, 0, 0, 0)
        except openai.APITimeoutError:
            logger.warning(
                "LLM APIがタイムアウトしました (質問: %.50s...)",
                question,
            )
            return (self._build_fallback_answer(question), 0.0, 0, 0, 0)
        except openai.APIConnectionError:
            logger.warning(
                "LLM APIへの接続に失敗しました (質問: %.50s...)",
                question,
            )
            return (self._build_fallback_answer(question), 0.0, 0, 0, 0)
        except openai.RateLimitError:
            logger.warning(
                "LLM APIのレート制限に達しました (質問: %.50s...)",
                question,
            )
            return (self._build_fallback_answer(question), 0.0, 0, 0, 0)
        except openai.APIStatusError as e:
            logger.error(
                "LLM APIがステータスコード %d を返しました (質問: %.50s...)",
                e.status_code,
                question,
                exc_info=True,
            )
            return (self._build_fallback_answer(question), 0.0, 0, 0, 0)

    def _prefers_english_response(self, question: str) -> bool:
        """英字を含む質問では英語の固定応答を優先する。"""
        return bool(_LATIN_LETTER_RE.search(question or ""))

    def _build_not_found_answer(self, question: str) -> str:
        if self._prefers_english_response(question):
            return ENGLISH_NOT_FOUND_ANSWER
        return JAPANESE_NOT_FOUND_ANSWER

    def _build_fallback_answer(self, question: str) -> str:
        if self._prefers_english_response(question):
            return ENGLISH_FALLBACK_ANSWER
        return JAPANESE_FALLBACK_ANSWER

    def _build_generation_messages(
        self,
        question: str,
        sources: list[SourceChunk],
    ) -> list[dict[str, str]]:
        """検索結果から生成用の system/user メッセージを組み立てる。"""
        # 検索結果を「参考情報」テキストに組み立てる
        context_parts: list[str] = []
        for i, src in enumerate(sources, start=1):
            location = src.source_file
            if src.payload.get("sheet_name"):
                location += f" > {src.payload['sheet_name']}"
            if src.payload.get("cell_range"):
                location += f" [{src.payload['cell_range']}]"
            context_parts.append(f"[Reference {i}] (source: {location})\n{src.text}")
        context_text = "\n---\n".join(context_parts)

        # ユーザーメッセージを組み立てる
        user_message = (
            f"Answer the question using only the reference information below.\n\n"
            f"Reference Information:\n{context_text}\n\n"
            "Constraints:\n"
            "- Be concise.\n"
            "- If the question is in English, answer only in English.\n"
            "- Include at least one exact citation label such as [Reference 1].\n"
            "- Prefer exact menu paths or action steps when they appear in the references.\n\n"
            f"Question: {question}"
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

    def _build_repair_messages(
        self,
        question: str,
        sources: list[SourceChunk],
        draft_answer: str,
    ) -> list[dict[str, str]]:
        """同一ソースを使って、言語・引用制約を満たすよう回答を修正する。"""
        context_parts: list[str] = []
        for i, src in enumerate(sources, start=1):
            location = src.source_file
            if src.payload.get("sheet_name"):
                location += f" > {src.payload['sheet_name']}"
            if src.payload.get("cell_range"):
                location += f" [{src.payload['cell_range']}]"
            context_parts.append(f"[Reference {i}] (source: {location})\n{src.text}")
        context_text = "\n---\n".join(context_parts)
        user_message = (
            "Rewrite the previous answer using only the same reference information.\n"
            "Do not perform another search.\n"
            "Fix any language mismatch, keep the answer concise, "
            "and include at least one exact citation label such as "
            "[Reference 1].\n\n"
            f"Reference Information:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            f"Previous Answer:\n{draft_answer}"
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

    def _needs_generation_repair(
        self,
        question: str,
        answer: str,
        sources: list[SourceChunk],
    ) -> bool:
        """明らかな制約違反がある場合のみ、同一コンテキストで 1 回だけ再生成する。"""
        if not sources or not answer.strip():
            return False
        if answer in {
            ENGLISH_NOT_FOUND_ANSWER,
            JAPANESE_NOT_FOUND_ANSWER,
            ENGLISH_FALLBACK_ANSWER,
            JAPANESE_FALLBACK_ANSWER,
        }:
            return False
        if self._prefers_english_response(question) and self._looks_non_english_answer(
            answer
        ):
            return True
        return not self._has_required_citation(answer)

    def _has_required_citation(self, answer: str) -> bool:
        """期待する [Reference N] 形式の引用が含まれているか判定する。"""
        return bool(_CITATION_RE.search(answer))

    def _looks_non_english_answer(self, answer: str) -> bool:
        """英語質問に対して明らかに非英語の回答になっていないかを緩く判定する。"""
        normalized = f" {answer.lower()} "
        if _NON_ENGLISH_SCRIPT_RE.search(normalized):
            return True
        return any(marker in normalized for marker in _NON_ENGLISH_HINTS)

    def _generate_with_openai(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, float, int, int, int]:
        """OpenAI-compatible Chat Completions API で回答を生成する。"""
        start = time.perf_counter()
        extra_body = build_chat_extra_body(
            base_url=self.openai_settings.openai_base_url,
            chat_think=self.openai_settings.chat_think,
        )
        response = self.openai_client.chat.completions.create(
            model=self.openai_settings.chat_model,
            messages=messages,
            temperature=self.openai_settings.chat_temperature,
            extra_body=extra_body,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0
        answer = response.choices[0].message.content or ""
        return (answer, latency_ms, prompt_tokens, completion_tokens, total_tokens)

    def _generate_with_ollama_native(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, float, int, int, int]:
        """Ollama native /api/chat を使って think オプションを確実に反映する。"""
        start = time.perf_counter()
        headers = {
            "Content-Type": "application/json",
            **build_auth_headers(self.openai_settings.openai_api_key),
        }

        response = httpx.post(
            build_ollama_native_chat_url(self.openai_settings.openai_base_url),
            headers=headers,
            json={
                "model": self.openai_settings.chat_model,
                "messages": messages,
                "think": self.openai_settings.chat_think,
                "options": build_ollama_native_options(
                    chat_temperature=self.openai_settings.chat_temperature,
                ),
                "stream": False,
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("ollama native response does not contain message")

        latency_ms = (time.perf_counter() - start) * 1000
        prompt_tokens = int(payload.get("prompt_eval_count") or 0)
        completion_tokens = int(payload.get("eval_count") or 0)
        total_tokens = prompt_tokens + completion_tokens
        answer = str(message.get("content") or "")
        return (answer, latency_ms, prompt_tokens, completion_tokens, total_tokens)

    def _should_use_ollama_native_chat(self) -> bool:
        """Ollama で think 制御が必要な場合のみ native API に切り替える。"""
        return self.openai_settings.chat_think is not None and is_ollama_base_url(
            self.openai_settings.openai_base_url
        )
