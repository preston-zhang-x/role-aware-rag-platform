"""
結構化ログ設定モジュール。
"""

import contextvars
import logging
import sys
import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class InterceptHandler(logging.Handler):
    """標準 logging → Loguru へのブリッジハンドラー。"""

    def emit(self, record: logging.LogRecord) -> None:
        # Loguru 側の対応レベルを取得する
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 呼び出し元のフレーム（ファイル名・行番号）を特定する
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """
    アプリケーション起動時に一度だけ呼ぶ。
    """
    # ── 1. Loguru をリセットして JSON sink を追加 ──
    logger.remove()  # デフォルト（stderr テキスト出力）を削除
    logger.add(
        sys.stderr,
        serialize=True,  # JSON 出力
        level="INFO",
        enqueue=True,  # スレッドセーフ
    )
    # ── 2. 標準 logging のルートを Loguru に接続 ──
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    # ── 3. サードパーティのロガーも統一 ──
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy"):
        third_party_logger = logging.getLogger(name)
        third_party_logger.handlers = [InterceptHandler()]
        third_party_logger.propagate = False


# リクエストID用のコンテキスト変数
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    全 HTTP リクエストに X-Request-ID を注入するミドルウェア。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. リクエストから X-Request-ID を取得、なければ新規生成
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # 2. コンテキストにセット
        request_id_ctx.set(rid)
        # 3. Loguru にバインドして、以降の全ログに request_id を付与
        with logger.contextualize(request_id=rid):
            logger.info(
                "request_started",
                method=request.method,
                path=str(request.url.path),
            )
            response = await call_next(request)
            logger.info(
                "request_finished",
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
            )
        # 4. レスポンスヘッダーにも返す（クライアントが追跡用に使える）
        response.headers["X-Request-ID"] = rid
        return response
