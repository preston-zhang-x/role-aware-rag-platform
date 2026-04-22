"""OpenAI互換モデルプロバイダーとOllama固有の挙動を扱うヘルパー。"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

OLLAMA_LOCAL_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "ollama",
}


def build_auth_headers(api_key: str | None) -> dict[str, str]:
    # APIキーがある場合のみ認証ヘッダーを生成する。
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def build_models_url(base_url: str) -> str:
    # ベースURLから models エンドポイントのURLを組み立てる。
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return f"{normalized}/models"
    return f"{normalized}/v1/models"


def is_ollama_base_url(base_url: str) -> bool:
    # URLがローカルまたはOllama向けホストかどうかを判定する。
    parsed = urlsplit(base_url)
    hostname = (parsed.hostname or "").lower()
    if hostname in OLLAMA_LOCAL_HOSTS:
        return parsed.port in {None, 11434}
    return hostname.endswith(".ollama")


def build_ollama_native_chat_url(base_url: str) -> str:
    # OpenAI互換URLから Ollama ネイティブの chat URL を生成する。
    parsed = urlsplit(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    native_path = f"{path}/api/chat" if path else "/api/chat"
    return urlunsplit((parsed.scheme, parsed.netloc, native_path, "", ""))


def build_chat_extra_body(
    *,
    base_url: str,
    chat_think: bool | None,
) -> dict[str, bool] | None:
    # Ollama利用時のみ think パラメーターを追加する。
    if chat_think is None or not is_ollama_base_url(base_url):
        return None
    return {"think": chat_think}


def build_ollama_native_options(
    *,
    chat_temperature: float | None,
) -> dict[str, float] | None:
    # Ollama native chat では生成制御を options 配下で渡す。
    if chat_temperature is None:
        return None
    return {"temperature": chat_temperature}
