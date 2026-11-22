"""Ask Corvalis — API server."""
from fastapi import FastAPI

from app import llm

app = FastAPI(title="Ask Corvalis")


@app.get("/api/health")
def health():
    return {"status": "ok", "ollama": llm.is_available()}
