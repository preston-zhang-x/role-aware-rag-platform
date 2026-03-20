"""BM25 による疎検索サービス。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from heapq import nlargest
from typing import Any

from qdrant_client.http.models import FieldCondition, Filter, MatchAny
from rank_bm25 import BM25Okapi
from sudachipy import dictionary
from sudachipy import tokenizer as sudachi_tokenizer

from app.clients.qdrant_client import get_qdrant_client

DEFAULT_COLLECTION = "documents"
DEFAULT_TOP_K = 5
# Qdrant の scroll API で 1 回に取得する件数。
SCROLL_BATCH_SIZE = 100
# BM25 では細かい語単位の一致を拾いたいため、最小粒度の SplitMode.A を使う。
_SUDACHI_SPLIT_MODE = sudachi_tokenizer.Tokenizer.SplitMode.A
# 記号や空白は検索語としての寄与が低いため除外する。
_IGNORED_PARTS_OF_SPEECH = {"補助記号", "空白"}

Payload = dict[str, Any]
_BM25_CACHE: dict[tuple[int, str, tuple[str, ...]], "BM25Service"] = {}


@dataclass
class BM25Hit:
    """BM25 検索でヒットした 1 件の結果。"""

    text: str
    source_file: str
    score: float
    chunk_index: int = 0
    payload: Payload = field(default_factory=dict)


@lru_cache(maxsize=1)
def _get_tokenizer() -> sudachi_tokenizer.Tokenizer:
    """Sudachi の tokenizer をキャッシュし、辞書の再読込を避ける。"""
    return dictionary.Dictionary(dict="core").create()


def tokenize(text: str) -> list[str]:
    """Sudachi を使ってテキストを分かち書きし、正規化する。"""
    if not text or not text.strip():
        return []

    tokens: list[str] = []
    for morpheme in _get_tokenizer().tokenize(text, _SUDACHI_SPLIT_MODE):
        # 句読点や空白を落として、BM25 に意味のある語だけを残す。
        if morpheme.part_of_speech()[0] in _IGNORED_PARTS_OF_SPEECH:
            continue

        normalized = morpheme.normalized_form().strip().lower()
        if normalized:
            tokens.append(normalized)

    return tokens


class BM25Service:
    """BM25 ベースのキーワード検索サービス。"""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        top_k: int = DEFAULT_TOP_K,
        qdrant_wrapper=None,
    ) -> None:
        self.collection_name = collection_name
        self.top_k = top_k
        self.qdrant_wrapper = qdrant_wrapper or get_qdrant_client()
        self._bm25: BM25Okapi | None = None
        self._corpus_texts: list[str] = []
        self._corpus_payloads: list[Payload] = []

    def build_index(self, user_roles: list[str] | None = None) -> int:
        """Qdrant からコーパスを読み込み、BM25 インデックスを構築する。"""
        texts, payloads = self._load_corpus_from_qdrant(user_roles)
        # 空文字列やトークン化できない文書はこの段階で除外しておく。
        tokenized_corpus, indexed_texts, indexed_payloads = self._prepare_corpus(
            texts,
            payloads,
        )

        if not tokenized_corpus:
            self._clear_index()
            return 0

        self._bm25 = BM25Okapi(tokenized_corpus)
        self._corpus_texts = indexed_texts
        self._corpus_payloads = indexed_payloads
        return len(indexed_texts)

    def search(self, query: str, top_k: int | None = None) -> list[BM25Hit]:
        """BM25 スコア順で関連度の高いチャンクを返す。"""
        if self._bm25 is None:
            return []

        limit = self.top_k if top_k is None else top_k
        if limit <= 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        # 全件 sort よりも上位件数だけ抜く方が意図が明確で無駄が少ない。
        ranked_indices = nlargest(
            min(limit, len(scores)),
            range(len(scores)),
            key=scores.__getitem__,
        )
        return self._build_hits(ranked_indices, scores)

    @property
    def is_indexed(self) -> bool:
        return self._bm25 is not None

    @property
    def corpus_size(self) -> int:
        return len(self._corpus_texts)

    def _clear_index(self) -> None:
        self._bm25 = None
        self._corpus_texts = []
        self._corpus_payloads = []

    def _prepare_corpus(
        self,
        texts: list[str],
        payloads: list[Payload],
    ) -> tuple[list[list[str]], list[str], list[Payload]]:
        # BM25 に投入する配列と、結果復元用の元データを同じ順序で保持する。
        tokenized_corpus: list[list[str]] = []
        indexed_texts: list[str] = []
        indexed_payloads: list[Payload] = []

        for text, payload in zip(texts, payloads):
            tokens = tokenize(text)
            if not tokens:
                continue

            tokenized_corpus.append(tokens)
            indexed_texts.append(text)
            indexed_payloads.append(payload)

        return tokenized_corpus, indexed_texts, indexed_payloads

    def _build_hits(self, ranked_indices: list[int], scores: Any) -> list[BM25Hit]:
        hits: list[BM25Hit] = []
        for index in ranked_indices:
            score = float(scores[index])
            # BM25 が 0 以下のものは関連なしとして返さない。
            if score <= 0:
                continue
            hits.append(self._build_hit(index, score))
        return hits

    def _build_hit(self, index: int, score: float) -> BM25Hit:
        payload = self._corpus_payloads[index]
        return BM25Hit(
            text=self._corpus_texts[index],
            source_file=payload.get("source_file", "unknown"),
            score=score,
            chunk_index=payload.get("chunk_index", 0),
            payload=payload,
        )

    def _load_corpus_from_qdrant(
        self,
        user_roles: list[str] | None = None,
    ) -> tuple[list[str], list[Payload]]:
        if not self.qdrant_wrapper.collection_exists(self.collection_name):
            return [], []

        texts: list[str] = []
        payloads: list[Payload] = []
        offset = None
        scroll_filter = self._build_role_filter(user_roles)

        while True:
            # ベクトルは不要なので payload のみをページング取得する。
            records, next_offset = self.qdrant_wrapper.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=SCROLL_BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for record in records:
                payload = record.payload or {}
                text = self._extract_text(payload).strip()
                if not text:
                    continue

                texts.append(text)
                payloads.append(payload)

            if next_offset is None:
                break

            offset = next_offset

        return texts, payloads

    def _build_role_filter(self, user_roles: list[str] | None) -> Filter | None:
        if not user_roles:
            return None

        # allowed_roles に 1 つでも一致するチャンクだけを対象にする。
        return Filter(
            must=[
                FieldCondition(
                    key="allowed_roles",
                    match=MatchAny(any=user_roles),
                )
            ]
        )

    def _extract_text(self, payload: Payload) -> str:
        node_content = payload.get("_node_content")
        if node_content is None:
            return str(payload.get("text", ""))

        # LlamaIndex が dict をそのまま返すケース。
        if isinstance(node_content, dict):
            return str(node_content.get("text", ""))

        # 文字列 JSON として保存されているケースが最も多い。
        if isinstance(node_content, str):
            try:
                parsed = json.loads(node_content)
            except json.JSONDecodeError:
                # 壊れた JSON でも生文字列を捨てずに返す。
                return node_content

            if isinstance(parsed, dict):
                return str(parsed.get("text", ""))
            return str(parsed)

        return str(node_content)


def get_cached_bm25_service(
    *,
    collection_name: str = DEFAULT_COLLECTION,
    user_roles: list[str] | None = None,
    qdrant_wrapper=None,
) -> BM25Service:
    """ロール条件ごとの BM25 インデックスを遅延構築して再利用する。"""
    wrapper = qdrant_wrapper or get_qdrant_client()
    cache_key = (id(wrapper), collection_name, _roles_cache_key(user_roles))
    service = _BM25_CACHE.get(cache_key)
    if service is None:
        service = BM25Service(
            collection_name=collection_name,
            qdrant_wrapper=wrapper,
        )
        service.build_index(user_roles)
        _BM25_CACHE[cache_key] = service
    return service


def invalidate_bm25_cache(collection_name: str | None = None) -> None:
    """指定コレクションに紐づく BM25 キャッシュを破棄する。"""
    if collection_name is None:
        _BM25_CACHE.clear()
        return

    stale_keys = [key for key in _BM25_CACHE if key[1] == collection_name]
    for key in stale_keys:
        _BM25_CACHE.pop(key, None)


def _roles_cache_key(user_roles: list[str] | None) -> tuple[str, ...]:
    if not user_roles:
        return ()
    return tuple(sorted(set(user_roles)))
