from __future__ import annotations

import importlib
from types import SimpleNamespace

import app.db.session as session_module


def test_db_session_import_is_lazy(monkeypatch) -> None:
    import sqlalchemy

    create_engine_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def unexpected_create_engine(*args, **kwargs):
        create_engine_calls.append((args, kwargs))
        return SimpleNamespace()

    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(sqlalchemy, "create_engine", unexpected_create_engine)

    reloaded = importlib.reload(session_module)

    assert create_engine_calls == []

    fake_engine = SimpleNamespace(name="engine")

    def fake_create_engine(*args, **kwargs):
        create_engine_calls.append((args, kwargs))
        return fake_engine

    monkeypatch.setattr(reloaded, "create_engine", fake_create_engine)
    reloaded.get_db_settings.cache_clear()
    reloaded.get_engine.cache_clear()
    reloaded.get_session_factory.cache_clear()

    assert reloaded.get_engine() is fake_engine
    assert reloaded.get_engine() is fake_engine
    assert create_engine_calls == [
        (
            ("sqlite+pysqlite:///:memory:",),
            {"pool_pre_ping": True},
        )
    ]
