"""RAG Service:检索增强生成的核心逻辑。
流程:Query → Embedding → Qdrant 检索 → 拼 Prompt → LLM 生成 → 返回结果。
"""

import json
from dataclasses import dataclass, field

from openai import OpenAI
from qdrant_client.http.models import FieldCondition, Filter, MatchAny

from app.clients.qdrant_client import get_qdrant_client
from app.core.config import openai_settings

DEFAULT_COLLECTION = "documents"
DEFAULT_TOP_K = 5

SYSTEM_PROMPT = (
    "あなたは社内ドキュメントに基づいて質問に答えるアシスタントです。\n"
    "以下の「参考情報」だけを使って回答してください。\n"
    "参考情報に答えがない場合は「ドキュメントに該当する情報が見つかりませんでした」と答えてください。\n"
    "回答には必ず出典（どのドキュメントの情報か）を明記してください。"
)


# ── 結果データクラス ─────────────────────────────────────────
@dataclass
class SourceChunk:
    """検索でヒットした1つのチャンクの情報。"""

    text: str
    source_file: str
    score: float
    chunk_index: int = 0


@dataclass
class RagResult:
    """RAG の最終結果。"""

    answer: str
    sources: list[SourceChunk] = field(default_factory=list)


# ── RAG Service 本体 ────────────────────────────────────────
class RagService:
    """RAG のコアロジックを実装するサービスクラス。"""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        top_k: int = DEFAULT_TOP_K,
        qdrant_wrapper=None,
    ) -> None:
        self.collection_name = collection_name
        self.top_k = top_k
        self.qdrant_wrapper = qdrant_wrapper or get_qdrant_client()
        # OpenAI クライアント初期化（Embedding + Chat 両方で使う）
        self.openai_client = OpenAI(
            api_key=openai_settings.openai_api_key,
            base_url=openai_settings.openai_base_url,
        )

    def ask(self, question: str, user_roles: list[str]) -> RagResult:
        """
        RAG のメインメソッド。質問を受け取り、回答を返す。
        """
        # 1. 質問をベクトルに変換（Embedding）
        query_vector = self._embed_query(question)
        # 2. Qdrant で類似チャンクを検索（Retrieval）
        sources = self._search(query_vector, user_roles)
        # 3. 検索結果がなければ早期リターン
        if not sources:
            return RagResult(
                answer="ドキュメントに該当する情報が見つかりませんでした。",
                sources=[],
            )
        # 4. Prompt を組み立てて LLM に投げる（Generation）
        answer = self._generate(question, sources)
        return RagResult(answer=answer, sources=sources)

    # ── Private メソッド ─────────────────────────────────────
    def _embed_query(self, text: str) -> list[float]:
        """
        テキストを Embedding ベクトルに変換する。
        """
        response = self.openai_client.embeddings.create(
            model=openai_settings.embedding_model,
            input=text,
            dimensions=openai_settings.embedding_dimensions,
        )
        return response.data[0].embedding

    def _search(
        self, query_vector: list[float], user_roles: list[str]
    ) -> list[SourceChunk]:
        """
        Qdrant からユーザーの権限に合った類似チャンクを検索する。
        """
        # ロールベースのフィルタを構築
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="allowed_roles",
                    match=MatchAny(any=user_roles),
                )
            ]
        )

        # Qdrant で検索実行
        results = self.qdrant_wrapper.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=self.top_k,
            with_payload=True,
        )

        # 検索結果をSourceChunkに変換
        sources: list[SourceChunk] = []
        for point in results.points:
            payload = point.payload or {}
            # LlamaIndex が保存したテキストは _node_content の中にある
            text = self._extract_text(payload)
            sources.append(
                SourceChunk(
                    text=text,
                    source_file=payload.get("source_file", "unknown"),
                    score=point.score,
                    chunk_index=payload.get("chunk_index", 0),
                )
            )
        return sources

    def _extract_text(self, payload: dict) -> str:
        """
        Qdrant の payload からテキストを取り出す。
        """
        node_content = payload.get("_node_content")
        if node_content:
            try:
                parsed = json.loads(node_content)
                return parsed.get("text", "")
            except (json.JSONDecodeError, TypeError):
                return str(node_content)
        return payload.get("text", "")

    def _generate(self, question: str, sources: list[SourceChunk]) -> str:
        """
        検索で得たチャンクを元に LLM で回答を生成する。
        """

        # 検索結果を「参考情報」テキストに組み立てる
        context_parts: list[str] = []
        for i, src in enumerate(sources, start=1):
            context_parts.append(f"【参考{i}】（出典: {src.source_file}）\n{src.text}")
        context_text = "\n---\n".join(context_parts)

        # ユーザーメッセージを組み立てる
        user_message = (
            f"以下の参考情報を元に質問に答えてください。\n\n"
            f"参考情報:\n{context_text}\n\n"
            f"質問: {question}"
        )

        # LLM に投げる（Chat Completion API）
        response = self.openai_client.chat.completions.create(
            model=openai_settings.chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,  # 低い＝事実に忠実、高い＝創造的
        )

        return response.choices[0].message.content or ""
