from fastapi import FastAPI
from app.api.v1.docs import router as docs_router
from app.api.v1.auth import router as auth_router

app = FastAPI(title="Role Aware RAG Platform")


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}

app.include_router(docs_router)
app.include_router(auth_router)