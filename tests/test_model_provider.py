from app.core.model_provider import (
    build_auth_headers,
    build_chat_extra_body,
    build_ollama_native_options,
    build_models_url,
    build_ollama_native_chat_url,
    is_ollama_base_url,
)


def test_build_auth_headers_omits_empty_key() -> None:
    assert build_auth_headers(None) == {}
    assert build_auth_headers("") == {}


def test_build_auth_headers_adds_bearer_token() -> None:
    assert build_auth_headers("ollama") == {"Authorization": "Bearer ollama"}


def test_build_models_url_appends_models_path() -> None:
    assert build_models_url("http://localhost:11434/v1") == (
        "http://localhost:11434/v1/models"
    )
    assert build_models_url("https://example.com/openai") == (
        "https://example.com/openai/v1/models"
    )


def test_is_ollama_base_url_detects_local_and_service_hosts() -> None:
    assert is_ollama_base_url("http://localhost:11434/v1") is True
    assert is_ollama_base_url("http://ollama:11434/v1") is True
    assert is_ollama_base_url("https://api.example.com/v1") is False


def test_build_ollama_native_chat_url_replaces_v1_suffix() -> None:
    assert build_ollama_native_chat_url("http://localhost:11434/v1") == (
        "http://localhost:11434/api/chat"
    )
    assert build_ollama_native_chat_url("http://localhost:11434/openai/v1") == (
        "http://localhost:11434/openai/api/chat"
    )


def test_build_chat_extra_body_only_for_ollama() -> None:
    assert build_chat_extra_body(
        base_url="http://localhost:11434/v1",
        chat_think=False,
    ) == {"think": False}
    assert (
        build_chat_extra_body(
            base_url="https://api.example.com/v1",
            chat_think=False,
        )
        is None
    )


def test_build_ollama_native_options_uses_temperature() -> None:
    assert build_ollama_native_options(chat_temperature=0.0) == {"temperature": 0.0}
    assert build_ollama_native_options(chat_temperature=0.2) == {"temperature": 0.2}
    assert build_ollama_native_options(chat_temperature=None) is None
    assert (
        build_chat_extra_body(
            base_url="http://localhost:11434/v1",
            chat_think=None,
        )
        is None
    )
