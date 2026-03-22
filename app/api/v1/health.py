from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.clients.qdrant_client import get_qdrant_client
from app.db.session import get_engine

router = APIRouter(prefix="/api/v1/health", tags=["health"])


def check_database() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


def check_qdrant() -> None:
    get_qdrant_client().check_connection()


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

    if all(value == "ok" for value in checks.values()):
        return {"status": "ok", "checks": checks}

    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "checks": checks},
    )


@router.get("")
def health():
    return readiness()
