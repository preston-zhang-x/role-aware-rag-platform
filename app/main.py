from fastapi import FastAPI
from app.api.v1.docs import router as docs_router


app = FastAPI(title="Role Aware RAG Platform")


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}

app.include_router(docs_router)
