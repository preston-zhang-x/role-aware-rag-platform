from __future__ import annotations

import pytest
from pydantic import ValidationError

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
