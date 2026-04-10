"""Cohere 互換の `/rerank` エンドポイントを提供するローカル rerank アダプター。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import ENV_FILE


class RerankAdapterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_api_key: str = "local-rerank"
    rerank_device: str = "cpu"
    rerank_max_length: int = Field(default=1024, gt=0)


@lru_cache(maxsize=1)
def get_rerank_adapter_settings() -> RerankAdapterSettings:
    return RerankAdapterSettings()


class RerankRequest(BaseModel):
    model: str
    query: str = Field(min_length=1)
    documents: list[str] = Field(default_factory=list)
    top_n: int = Field(gt=0)
    max_tokens_per_doc: int = Field(default=1024, gt=0)


class RerankResultItem(BaseModel):
    index: int
    relevance_score: float


class RerankResponse(BaseModel):
    results: list[RerankResultItem]


class HuggingFaceRerankerBackend:
    """Hugging Face の cross-encoder reranker を包む軽量ラッパー。"""

    def __init__(self, model_name: str, device: str = "cpu", max_length: int = 1024):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing rerank-adapter dependencies. "
                "Install them with: uv sync --extra rerank"
            ) from exc

        resolved_device = device
        # CUDA 指定でも利用不可なら安全に CPU へフォールバックする。
        if device.startswith("cuda") and not torch.cuda.is_available():
            resolved_device = "cpu"

        self._torch = torch
        self.device_label = resolved_device
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(resolved_device)
        self.model.eval()

    def score(
        self,
        query: str,
        documents: list[str],
        *,
        max_tokens_per_doc: int,
    ) -> list[float]:
        if not documents:
            return []

        # モデル上限とリクエスト上限の小さい方を実際の入力長として使う。
        effective_max_length = min(self.max_length, max_tokens_per_doc)
        encoded = self.tokenizer(
            [query] * len(documents),
            documents,
            padding=True,
            truncation=True,
            max_length=effective_max_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device_label) for key, value in encoded.items()}
        # 推論専用モードでスコアだけを計算する。
        with self._torch.inference_mode():
            logits = self.model(**encoded).logits.reshape(-1)
        return logits.float().cpu().tolist()


@lru_cache(maxsize=1)
def get_backend() -> HuggingFaceRerankerBackend:
    settings = get_rerank_adapter_settings()
    return HuggingFaceRerankerBackend(
        model_name=settings.rerank_model,
        device=settings.rerank_device,
        max_length=settings.rerank_max_length,
    )


def _require_authorization(authorization: str | None, expected_api_key: str) -> None:
    # Cohere 互換の Bearer 認証を簡易的に検証する。
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
        )


app = FastAPI(title="Rerank Adapter")


@app.get("/health")
def health() -> Any:
    settings = get_rerank_adapter_settings()
    try:
        # ヘルスチェック時にバックエンド初期化可否も合わせて確認する。
        backend = get_backend()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "model": settings.rerank_model,
                "detail": f"{exc.__class__.__name__}: {exc}",
            },
        )

    return {
        "status": "ok",
        "model": settings.rerank_model,
        "device": backend.device_label,
    }


@app.post("/rerank", response_model=RerankResponse)
def rerank(
    request: RerankRequest,
    authorization: str | None = Header(default=None),
) -> RerankResponse:
    settings = get_rerank_adapter_settings()
    _require_authorization(authorization, settings.rerank_api_key)
    if request.model != settings.rerank_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported model '{request.model}'. "
                f"Expected '{settings.rerank_model}'."
            ),
        )

    backend = get_backend()
    scores = backend.score(
        request.query,
        request.documents,
        max_tokens_per_doc=request.max_tokens_per_doc,
    )
    top_n = min(request.top_n, len(scores))
    # スコアの高い順に並べ、要求件数だけ返す。
    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda index: scores[index],
        reverse=True,
    )[:top_n]

    return RerankResponse(
        results=[
            RerankResultItem(
                index=index,
                relevance_score=float(scores[index]),
            )
            for index in ranked_indexes
        ]
    )


def main() -> None:
    uvicorn.run(
        "app.rerank_adapter:app",
        host="0.0.0.0",
        port=8090,
        reload=False,
    )


if __name__ == "__main__":
    main()
