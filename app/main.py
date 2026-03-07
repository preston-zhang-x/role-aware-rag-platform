from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.docs import router as docs_router
from app.api.v1.health import router as health_router

app = FastAPI(title="Role Aware RAG Platform")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(docs_router)
