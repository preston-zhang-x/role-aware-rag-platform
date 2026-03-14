"""RAG 検索問答 API ルーター。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
    role: str = Field(
        default="viewer",
        description="ユーザーのロール（権限フィルタリング用）",
        examples=["admin", "editor", "viewer"],
    )


class SourceOut(BaseModel):
    text: str
    source_file: str
    score: float
    chunk_index: int


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


# ── エンドポイント ──────────────────────────────────────────
@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
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
            user_roles=[request.role],
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
                )
                for src in result.sources
            ],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG パイプラインでエラーが発生しました: {str(e)}",
        ) from e
