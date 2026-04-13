from __future__ import annotations

import asyncio
import importlib
import logging
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, TypedDict, cast

from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

import app.main as main_module
from app.core import logging as logging_module


class FakeLoguruLogger:
    def __init__(self) -> None:
        self.level_result = "INFO"
        self.raise_level_error = False
        self.logged_messages: list[tuple[object, str]] = []
        self.opt_calls: list[dict[str, object]] = []
        self.remove_calls = 0
        self.add_calls: list[tuple[object, dict[str, object]]] = []
        self.context_calls: list[dict[str, object]] = []
        self.info_calls: list[tuple[str, dict[str, object]]] = []

    def level(self, name: str) -> SimpleNamespace:
        if self.raise_level_error:
            raise ValueError(name)
        return SimpleNamespace(name=self.level_result)

    def opt(self, *, depth: int, exception: object):
        self.opt_calls.append({"depth": depth, "exception": exception})
        return self

    def log(self, level: object, message: str) -> None:
        self.logged_messages.append((level, message))

    def remove(self) -> None:
        self.remove_calls += 1

    def add(self, sink: object, **kwargs: object) -> None:
        self.add_calls.append((sink, kwargs))

    @contextmanager
    def contextualize(self, **kwargs: object):
        self.context_calls.append(kwargs)
        yield

    def info(self, message: str, **kwargs: object) -> None:
        self.info_calls.append((message, kwargs))


class FakeStdLogger:
    def __init__(self) -> None:
        self.handlers: list[logging.Handler] = []
        self.propagate = True


class BasicConfigCall(TypedDict):
    handlers: list[logging.Handler]
    level: int
    force: bool


def make_frame(filename: str, back: object = None) -> SimpleNamespace:
    return SimpleNamespace(
        f_code=SimpleNamespace(co_filename=filename),
        f_back=back,
    )


def make_request(
    *, path: str, method: str = "GET", headers: list[tuple[bytes, bytes]] | None = None
) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_intercept_handler_emits_to_loguru_with_matching_level(monkeypatch) -> None:
    fake_logger = FakeLoguruLogger()
    monkeypatch.setattr(logging_module, "logger", fake_logger)

    outer_frame = make_frame("caller.py")
    logging_frame = make_frame(logging.__file__, outer_frame)
    monkeypatch.setattr(logging_module.logging, "currentframe", lambda: logging_frame)

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    logging_module.InterceptHandler().emit(record)

    assert fake_logger.opt_calls == [{"depth": 3, "exception": None}]
    assert fake_logger.logged_messages == [("INFO", "hello world")]


def test_intercept_handler_falls_back_to_levelno_for_unknown_level(monkeypatch) -> None:
    fake_logger = FakeLoguruLogger()
    fake_logger.raise_level_error = True
    monkeypatch.setattr(logging_module, "logger", fake_logger)
    monkeypatch.setattr(logging_module.logging, "currentframe", lambda: None)
    exc_info: Any = None
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test",
        level=15,
        pathname=__file__,
        lineno=20,
        msg="fallback path",
        args=(),
        exc_info=exc_info,
    )
    record.levelname = "CUSTOM"

    logging_module.InterceptHandler().emit(record)

    assert fake_logger.opt_calls == [{"depth": 2, "exception": exc_info}]
    assert fake_logger.logged_messages == [(15, "fallback path")]


def test_setup_logging_wires_loguru_and_third_party_loggers(monkeypatch) -> None:
    fake_logger = FakeLoguruLogger()
    basic_config_calls: list[BasicConfigCall] = []
    third_party_loggers = {
        name: FakeStdLogger()
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy")
    }
    original_get_logger = logging.getLogger

    monkeypatch.setenv("LOGURU_ENQUEUE", "true")
    monkeypatch.setattr(logging_module, "logger", fake_logger)
    monkeypatch.setattr(
        logging_module.logging,
        "basicConfig",
        lambda **kwargs: basic_config_calls.append(cast(BasicConfigCall, kwargs)),
    )
    monkeypatch.setattr(
        logging_module.logging,
        "getLogger",
        lambda name=None: (
            third_party_loggers[name]
            if name in third_party_loggers
            else original_get_logger(name)
        ),
    )

    logging_module.setup_logging()

    assert fake_logger.remove_calls == 1
    assert fake_logger.add_calls == [
        (
            logging_module.sys.stderr,
            {
                "serialize": True,
                "level": "INFO",
                "enqueue": True,
            },
        )
    ]
    assert len(basic_config_calls) == 1
    assert basic_config_calls[0]["level"] == 0
    assert basic_config_calls[0]["force"] is True
    assert len(basic_config_calls[0]["handlers"]) == 1
    assert isinstance(
        basic_config_calls[0]["handlers"][0],
        logging_module.InterceptHandler,
    )

    for configured_logger in third_party_loggers.values():
        assert len(configured_logger.handlers) == 1
        assert isinstance(
            configured_logger.handlers[0], logging_module.InterceptHandler
        )
        assert configured_logger.propagate is False


async def noop_app(scope: Scope, receive: Receive, send: Send) -> None:
    del scope, receive, send


def test_request_id_middleware_uses_existing_header(monkeypatch) -> None:
    fake_logger = FakeLoguruLogger()
    monkeypatch.setattr(logging_module, "logger", fake_logger)
    monkeypatch.setattr(logging_module.uuid, "uuid4", lambda: "generated-but-unused")

    middleware = logging_module.RequestIdMiddleware(app=noop_app)
    request = make_request(
        path="/health",
        headers=[(b"x-request-id", b"req-123")],
    )

    async def call_next(_: Request) -> Response:
        assert logging_module.request_id_ctx.get() == "req-123"
        return Response(status_code=204)

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.headers["X-Request-ID"] == "req-123"
    assert fake_logger.context_calls == [{"request_id": "req-123"}]
    assert fake_logger.info_calls == [
        ("request_started", {"method": "GET", "path": "/health"}),
        (
            "request_finished",
            {"method": "GET", "path": "/health", "status_code": 204},
        ),
    ]
    logging_module.request_id_ctx.set("-")


def test_request_id_middleware_generates_header_when_missing(monkeypatch) -> None:
    fake_logger = FakeLoguruLogger()
    monkeypatch.setattr(logging_module, "logger", fake_logger)
    monkeypatch.setattr(logging_module.uuid, "uuid4", lambda: "generated-456")

    middleware = logging_module.RequestIdMiddleware(app=noop_app)
    request = make_request(path="/docs", method="POST")

    async def call_next(_: Request) -> Response:
        assert logging_module.request_id_ctx.get() == "generated-456"
        return Response(status_code=201)

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.headers["X-Request-ID"] == "generated-456"
    assert fake_logger.context_calls == [{"request_id": "generated-456"}]
    assert fake_logger.info_calls == [
        ("request_started", {"method": "POST", "path": "/docs"}),
        (
            "request_finished",
            {"method": "POST", "path": "/docs", "status_code": 201},
        ),
    ]
    logging_module.request_id_ctx.set("-")


def test_app_main_import_defers_logging_setup_until_startup(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(logging_module, "setup_logging", lambda: calls.append("setup"))

    reloaded = importlib.reload(main_module)

    assert calls == []

    with TestClient(reloaded.app):
        pass

    assert calls == ["setup"]
