import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.clients.qdrant_client import get_qdrant_client
from app.core.config import get_openai_settings, get_retrieval_settings
from app.core.model_provider import build_auth_headers, build_models_url
from app.db.session import get_engine

router = APIRouter(prefix="/api/v1/health", tags=["health"])
DEFAULT_TIMEOUT_SECONDS = 5.0


def check_database() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


def check_qdrant() -> None:
    get_qdrant_client().check_connection()


def _build_model_aliases(model_id: str) -> set[str]:
    aliases = {model_id}
    if model_id.endswith(":latest"):
        aliases.add(model_id[: -len(":latest")])
    return aliases


def check_model_provider() -> None:
    settings = get_openai_settings()
    response = httpx.get(
        build_models_url(settings.openai_base_url),
        headers=build_auth_headers(settings.openai_api_key),
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    raw_models = payload.get("data")
    if not isinstance(raw_models, list):
        raise ValueError("model provider returned an unexpected payload")

    available_models = set()
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str):
            available_models.update(_build_model_aliases(model_id))
    required_models = {
        settings.chat_model,
        settings.embedding_model,
    }
    missing_models = sorted(
        model for model in required_models if model not in available_models
    )
    if missing_models:
        raise ValueError(
            "missing required models: " + ", ".join(missing_models)
        )


def check_reranker_service() -> None:
    settings = get_retrieval_settings()
    if settings.retrieval_mode != "hybrid_rerank":
        return
    if not settings.rerank_base_url:
        raise ValueError("RERANK_BASE_URL is not configured")

    response = httpx.get(
        f"{settings.rerank_base_url.rstrip('/')}/health",
        headers=build_auth_headers(settings.rerank_api_key),
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise ValueError("reranker health check did not return ok")
    model_name = payload.get("model")
    if settings.rerank_model and model_name != settings.rerank_model:
        raise ValueError(
            "reranker model mismatch: "
            f"expected {settings.rerank_model}, got {model_name}"
        )


@router.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness():
    checks: dict[str, str] = {}

    try:
        check_database()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        check_qdrant()
        checks["qdrant"] = "ok"
    except Exception as exc:
        checks["qdrant"] = f"error: {exc.__class__.__name__}"

    try:
        check_model_provider()
        checks["models"] = "ok"
    except Exception as exc:
        checks["models"] = f"error: {exc.__class__.__name__}"

    try:
        check_reranker_service()
        checks["reranker"] = "ok"
    except Exception as exc:
        checks["reranker"] = f"error: {exc.__class__.__name__}"

    if all(value == "ok" for value in checks.values()):
        return {"status": "ok", "checks": checks}

    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "checks": checks},
    )


@router.get("")
def health():
    return readiness()
