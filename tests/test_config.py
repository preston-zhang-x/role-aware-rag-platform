from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

import app.core.config as config_module
from app.core.config import RetrievalSettings


def test_retrieval_settings_loads_strategy_and_top_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RETRIEVAL_MODE", "vector")
    monkeypatch.setenv("TOP_K", "3")

    settings = RetrievalSettings()

    assert settings.retrieval_mode == "vector"
    assert settings.top_k == 3


def test_retrieval_settings_rejects_invalid_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RETRIEVAL_MODE", "invalid_mode")

    with pytest.raises(ValidationError):
        RetrievalSettings()


def test_retrieval_settings_rejects_non_positive_top_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOP_K", "0")

    with pytest.raises(ValidationError):
        RetrievalSettings()


def test_config_import_does_not_instantiate_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_calls: list[str] = []

    def fail_if_called(self, *args, **kwargs) -> None:
        init_calls.append(type(self).__name__)
        raise AssertionError("settings should not be instantiated during module import")

    monkeypatch.setattr(BaseSettings, "__init__", fail_if_called)

    importlib.reload(config_module)

    assert init_calls == []


def test_settings_getters_load_from_repo_root_env_when_cwd_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root / "app")
    config_module.get_openai_settings.cache_clear()
    config_module.get_retrieval_settings.cache_clear()

    openai_settings = config_module.get_openai_settings()
    retrieval_settings = config_module.get_retrieval_settings()

    assert openai_settings.openai_base_url
    assert openai_settings.embedding_model
    assert retrieval_settings.top_k > 0
