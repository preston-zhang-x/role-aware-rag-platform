from fastapi import FastAPI


app = FastAPI(title="Role Aware RAG Platform")


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
