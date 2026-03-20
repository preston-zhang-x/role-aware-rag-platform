"""ハイブリッド検索統合: Vector + BM25 の検索結果を RRF アルゴリズムで統合し、順位付けする。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services.bm25_service import BM25Hit

# ── RRF のデフォルトパラメータ ─────────────────────────────────
DEFAULT_RRF_K = 60  # RRF の平滑化定数。論文で推奨されている値
DEFAULT_TOP_K = 5  # 最終的に返す件数

Payload = dict[str, Any]


class VectorHit(Protocol):
    text: str
    source_file: str
    score: float
    chunk_index: int
    payload: Payload


# ── 融合結果のデータクラス ──────────────────────────────────
@dataclass
class HybridChunk:
    """融合後の 1 件のチャンク。各検索路のスコアも保持する。"""

    text: str
    source_file: str
    rrf_score: float
    chunk_index: int = 0
    vector_score: float = 0.0
    bm25_score: float = 0.0
    payload: Payload = field(default_factory=dict)


# ── ヘルパー関数 ─────────────────────────────────────────────
def _make_key(source_file: str, chunk_index: int) -> str:
    """チャンクの一意識別キー。source_file + chunk_index で重複を検出する。"""
    return f"{source_file}::{chunk_index}"


def _empty_entry(text: str, source_file: str, chunk_index: int) -> dict:
    """merged 辞書の初期エントリ"""
    return {
        "text": text,
        "source_file": source_file,
        "chunk_index": chunk_index,
        "rrf_score": 0.0,
        "vector_score": 0.0,
        "bm25_score": 0.0,
        "payload": {},
    }


def reciprocal_rank_fusion(
    vector_hits: list[VectorHit],
    bm25_hits: list[BM25Hit],
    k: int = DEFAULT_RRF_K,
    top_k: int = DEFAULT_TOP_K,
) -> list[HybridChunk]:
    """
    2 路の検索結果を RRF で融合し、スコア順にソートして返す。
    """
    # 1. 各チャンクを一意に識別するキーで辞書に集約する
    merged: dict[str, dict] = {}

    # 2. Vector 検索結果を登録
    for rank, hit in enumerate(vector_hits, start=1):
        doc_key = _make_key(hit.source_file, hit.chunk_index)
        entry = merged.setdefault(
            doc_key, _empty_entry(hit.text, hit.source_file, hit.chunk_index)
        )
        entry["rrf_score"] += 1.0 / (k + rank)
        entry["vector_score"] = hit.score
        if not entry["payload"]:
            entry["payload"] = dict(hit.payload or {})

    # 3. BM25 検索結果を登録
    for rank, hit in enumerate(bm25_hits, start=1):
        doc_key = _make_key(hit.source_file, hit.chunk_index)
        entry = merged.setdefault(
            doc_key, _empty_entry(hit.text, hit.source_file, hit.chunk_index)
        )
        entry["rrf_score"] += 1.0 / (k + rank)
        entry["bm25_score"] = hit.score
        if not entry["payload"]:
            entry["payload"] = dict(hit.payload or {})

    # 4. dict → HybridChunk に変換してスコア降順にソート
    fused = [
        HybridChunk(
            text=entry["text"],
            source_file=entry["source_file"],
            rrf_score=entry["rrf_score"],
            chunk_index=entry["chunk_index"],
            vector_score=entry["vector_score"],
            bm25_score=entry["bm25_score"],
            payload=dict(entry["payload"]),
        )
        for entry in merged.values()
    ]
    # sorted は新しいリストを返す（元リストは変更しない）
    fused.sort(key=lambda c: c.rrf_score, reverse=True)
    return fused[:top_k]
