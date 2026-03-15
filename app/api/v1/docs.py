from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.models.document import Document
from app.db.models.user import UserRole
from app.db.session import get_db

# ================================================================================
# ドキュメント管理 API ルーター
# ドキュメントの作成、取得、更新、削除操作を管理（ロールベースアクセス制御対応）
# ================================================================================

router = APIRouter(prefix="/api/v1/docs", tags=["docs"])


# ドキュメント基本スキーマ（タイトル、内容）
class DocBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


# ドキュメント作成用スキーマ
class DocCreate(DocBase):
    pass


# ドキュメント更新用スキーマ（全フィールド省略可能）
class DocUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)


# ドキュメント出力スキーマ（ID、タイムスタンプ含む）
class DocOut(DocBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# ドキュメント作成エンドポイント（管理者・編集者のみ）
@router.post(
    "/",
    response_model=DocOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))],
)
def create_doc(payload: DocCreate, db: Session = Depends(get_db)) -> Document:
    doc = Document(title=payload.title, content=payload.content)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ドキュメント一覧取得エンドポイント（認証ユーザーのみ、ページネーション対応）
@router.get(
    "/",
    response_model=list[DocOut],
    dependencies=[Depends(get_current_user)],
)
def list_docs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Document]:
    stmt = select(Document).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


# ドキュメント単件取得エンドポイント（認証ユーザーのみ）
@router.get(
    "/{doc_id}",
    response_model=DocOut,
    dependencies=[Depends(get_current_user)],
)
def get_doc(doc_id: int, db: Session = Depends(get_db)) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ドキュメント更新エンドポイント（管理者・編集者のみ）
@router.put(
    "/{doc_id}",
    response_model=DocOut,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))],
)
def update_doc(
    doc_id: int, payload: DocUpdate, db: Session = Depends(get_db)
) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc, field, value)

    db.commit()
    db.refresh(doc)
    return doc


# ドキュメント削除エンドポイント（管理者のみ）
@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def delete_doc(doc_id: int, db: Session = Depends(get_db)) -> None:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(doc)
    db.commit()
    return None
