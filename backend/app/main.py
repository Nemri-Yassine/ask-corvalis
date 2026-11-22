"""Ask Corvalis — API server."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db, llm
from app.ingest import get_chunks, ingest_if_empty
from app.search import Index, chunk_text

# Filled at startup.
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    ingest_if_empty(conn)  # only does work on the very first start
    state["conn"] = conn
    state["rules_index"] = Index(get_chunks(conn), chunk_text)
    yield
    conn.close()


app = FastAPI(title="Ask Corvalis", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "ollama": llm.is_available()}
