from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi import status as http_status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_security_settings
from app.db.models.user import User, UserRole
from app.db.session import get_db

# ================================================================================
# セキュリティ設定とJWT トークン管理のモジュール
# ユーザー認証、パスワードハッシング、トークン生成・検証を管理
# ================================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    sub: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    security_settings = get_security_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=security_settings.access_token_expire_minutes)
    )
    # トークンペイロード（含有データ）
    payload = {
        "sub": subject,  # ユーザーID
        "exp": expire,  # 有効期限
    }
    return jwt.encode(
        payload,
        security_settings.secret_key,
        algorithm=security_settings.algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    security_settings = get_security_settings()
    # トークン検証失敗時の HTTP 応答例外を定義（401 Unauthorized）
    credentials_exception = HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # トークンを署名検証・復号し、ペイロードを取得
        payload = jwt.decode(
            token,
            security_settings.secret_key,
            algorithms=[security_settings.algorithm],
        )
    except jwt.InvalidTokenError as exc:
        # 署名エラー、期限切れ、形式不正などで例外を発生させ、401を返す
        raise credentials_exception from exc
    # ペイロードから ユーザーID（"sub"キー）を取得
    username = payload.get("sub")
    if not username:
        # "sub"なし（データ破損）の場合も 401 を返す
        raise credentials_exception
    return TokenPayload(sub=username)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: "Session" = Depends(get_db),
) -> User:
    token_payload = decode_access_token(token)

    user = db.execute(
        select(User).where(User.username == token_payload.sub)
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return role_checker
