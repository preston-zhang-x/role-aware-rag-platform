"""
統一エラーモデル。
すべてのビジネス例外は AppError を継承し、
グローバルなハンドラーが {"code": "ERR_xxx", "message": "..."} を返す。
"""
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

class UnauthorizedError(AppError): 
    """認証失敗（401）。"""
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            code="ERR_UNAUTHORIZED",
            message=message,
            status_code=401,
        )

class ForbiddenError(AppError):
    """権限不足（403）。"""
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(
            code="ERR_FORBIDDEN",
            message=message,
            status_code=403,
        )

class BadRequestError(AppError):
    """リクエスト不正（400）。"""
    def __init__(self, message: str = "Bad request") -> None:
        super().__init__(
            code="ERR_BAD_REQUEST",
            message=message,
            status_code=400,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """
    AppError を捕捉して統一フォーマットの JSON を返す。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
        },
    )

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    未捕捉の例外をキャッチして 500 を返す。
    """
    return JSONResponse(
        status_code=500,
        content={
            "code": "ERR_INTERNAL",
            "message": "Internal server error",
        },
    )