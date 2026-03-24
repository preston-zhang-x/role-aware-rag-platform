"""
統一エラーモデル。
すべてのビジネス例外は AppError を継承し、
グローバルなハンドラーが {"code": "ERR_xxx", "message": "..."} を返す。
"""
from pyexpat.errors import messages
from fastapi import Request
from fastapi.responses import JSONResponse

class AppError(Exception):
    """アプリケーション共通のビジネス例外基底クラス。"""
    def __init__(
      self,
      code: str = "ERR_UNKNOWN",
      message: str = "An unexpected error occurred",
      status_code: int = 500,
    ) -> None:
      super().__init__(message)
      self.code = code
      self.message = message
      self.status_code = status_code

class NotFoundError(AppError):
    """リソースが見つからない場合（404）。"""
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            code = "ERR_NOT_FOUND",
            message = message,
            status_code = 404,
        )

    