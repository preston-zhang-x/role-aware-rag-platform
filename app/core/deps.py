"""
FastAPI の依存関係をまとめて定義するモジュール。

認証済みユーザーの取得や、ロールベースのアクセス制御で使う。
"""

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.db.models.user import User, UserRole


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """現在の認証済みユーザーを返す。"""
    return current_user


def require_role(*allowed_roles: UserRole):
    """指定したロールを持つユーザーだけにアクセスを許可する。"""

    def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        """ユーザーのロールを検証し、許可されていればユーザーを返す。"""
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ロール '{current_user.role.value}' ではこのリソースにアクセスできません。"
                f"必要なロール: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker
