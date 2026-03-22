from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.docs import router as docs_router
from app.api.v1.health import router as health_router
from app.api.v1.rag import router as rag_router
from app.core.logging import RequestIdMiddleware, setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield


app = FastAPI(title="Role Aware RAG Platform", lifespan=lifespan)

app.add_middleware(RequestIdMiddleware)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(docs_router)
app.include_router(rag_router)
