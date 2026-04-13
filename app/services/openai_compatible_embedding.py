"""カスタムモデル名に対応した OpenAI 互換プロバイダー向け埋め込みアダプター。"""

from __future__ import annotations

from typing import Any

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.bridge.pydantic import Field, PrivateAttr
from openai import AsyncOpenAI, OpenAI


class OpenAICompatibleEmbedding(BaseEmbedding):
    """OpenAI 互換のローカルプロバイダー向け BaseEmbedding 実装。

    llama-index 標準の OpenAIEmbedding と異なり、Ollama の `bge-m3` のような
    任意のカスタムモデル名を受け取れるようにしている。
    """

    api_key: str | None = Field(default=None, description="プロバイダー用の API キー。")
    api_base: str = Field(description="OpenAI 互換 API のベース URL。")
    dimensions: int | None = Field(
        default=None,
        description="出力ベクトル次元数。未指定の場合はプロバイダー既定値を使う。",
    )
    timeout: float = Field(default=60.0, ge=0.0)

    _client: OpenAI = PrivateAttr()
    _aclient: AsyncOpenAI = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        # 同期・非同期の両方の呼び出し経路で同じ接続設定を使う。
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=self.timeout,
        )
        self._aclient = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=self.timeout,
        )

    def _request_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        # dimensions は対応プロバイダーのみへ明示的に渡す。
        if self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        return kwargs

    def _normalize_text(self, text: str) -> str:
        # 改行を空白へ正規化し、埋め込み API へ安定した入力を渡す。
        return text.replace("\n", " ")

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._get_text_embedding(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return await self._aget_text_embedding(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embeddings([text])[0]

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return (await self._aget_text_embeddings([text]))[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        normalized = [self._normalize_text(text) for text in texts]
        # llama-index が保持する model_name をそのまま OpenAI 互換 API に渡す。
        response = self._client.embeddings.create(
            model=self.model_name,
            input=normalized,
            **self._request_kwargs(),
        )
        return [item.embedding for item in response.data]

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        normalized = [self._normalize_text(text) for text in texts]
        response = await self._aclient.embeddings.create(
            model=self.model_name,
            input=normalized,
            **self._request_kwargs(),
        )
        return [item.embedding for item in response.data]
