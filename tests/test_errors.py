import json
import pytest
import asyncio
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import (
    AppError,
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    BadRequestError,
    app_error_handler,
    generic_exception_handler,
)


def test_app_error_base_class():
    """テスト：基底クラス（AppError）の初期化とプロパティ"""
    err = AppError(code="ERR_CUSTOM", message="Custom Msg", status_code=501)

    assert err.code == "ERR_CUSTOM"
    assert err.message == "Custom Msg"
    assert err.status_code == 501

    assert str(err) == "Custom Msg"


def test_not_found_error():
    """テスト：404 サブクラス（NotFoundError）"""
    err = NotFoundError()
    assert err.code == "ERR_NOT_FOUND"
    assert err.message == "Resource not found"
    assert err.status_code == 404

    err2 = NotFoundError(message="User info missing")
    assert err2.message == "User info missing"


def test_unauthorized_error():
    """テスト：401 サブクラス"""
    err = UnauthorizedError()
    assert err.code == "ERR_UNAUTHORIZED"
    assert err.status_code == 401


def test_forbidden_error():
    """テスト：403 サブクラス"""
    err = ForbiddenError()
    assert err.code == "ERR_FORBIDDEN"
    assert err.status_code == 403


def test_bad_request_error():
    """テスト：400 サブクラス"""
    err = BadRequestError()
    assert err.code == "ERR_BAD_REQUEST"
    assert err.status_code == 400


def test_app_error_handler():
    """テスト：グローバル AppError ハンドラー"""

    mock_request = Request(scope={"type": "http", "method": "GET"})
    exc = AppError(code="ERR_TEST", message="A test error", status_code=418)

    response = asyncio.run(app_error_handler(mock_request, exc))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 418

    body = json.loads(response.body)
    assert body["code"] == "ERR_TEST"
    assert body["message"] == "A test error"


def test_generic_exception_handler():
    """テスト：未捕捉例外用のルートハンドラー"""

    mock_request = Request(scope={"type": "http", "method": "GET"})
    exc = ValueError("Some weird internal bug")

    response = asyncio.run(generic_exception_handler(mock_request, exc))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 500

    body = json.loads(response.body)
    assert body["code"] == "ERR_INTERNAL"
    assert body["message"] == "Internal server error"
