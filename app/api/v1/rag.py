"""RAG 検索問答 API ルーター。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import get_current_active_user
from app.db.models.user import User
from app.services.rag_service import RagService

# ── Router 定義 ─────────────────────────────────────────────
router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


# ── Request / Response スキーマ ──────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="検索対象の質問文",
        examples=["売上レポートの作成方法は？"],
    )


class SourceOut(BaseModel):
    text: str
    source_file: str
    score: float
    chunk_index: int
    sheet_name: str | None = None
    cell_range: str | None = None
    content_type: str | None = None


class MetadataOut(BaseModel):
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    metadata: MetadataOut


# ── エンドポイント ──────────────────────────────────────────
@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, current_user: User = Depends(get_current_active_user)):
    """
    RAG 検索問答エンドポイント。

    1. question を受け取る
    2. RagService.ask() を呼んで RAG パイプラインを実行
    3. 回答とソース情報を返す
    """
    try:
        # RagService をインスタンス化して呼び出す
        service = RagService()
        result = service.ask(
            question=request.question,
            user_roles=[current_user.role.value],
        )

        # 結果を Response DTO に変換
        return AskResponse(
            answer=result.answer,
            sources=[
                SourceOut(
                    text=src.text,
                    source_file=src.source_file,
                    score=src.score,
                    chunk_index=src.chunk_index,
                    sheet_name=src.payload.get("sheet_name"),
                    cell_range=src.payload.get("cell_range"),
                    content_type=src.payload.get("content_type"),
                )
                for src in result.sources
            ],
            metadata=MetadataOut(
                latency_ms=result.latency_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
            ),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG パイプラインでエラーが発生しました: {str(e)}",
        ) from e
