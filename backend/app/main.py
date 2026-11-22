"""Ask Corvalis — API server."""
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import db, llm
from app.ingest import get_chunks, ingest_if_empty
from app.search import Index, chunk_text

MAX_QUESTION_LENGTH = 500
TOP_K = 3
SOURCE_RATIO = 0.5  # a source is shown if it scores at least half the best one
RULES_NOT_FOUND = (
    "I couldn't find this in the Corvalis policies. Please ask HR (hr@corvalis.be)."
)

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


# --- Request / response shapes ----------------------------------------------

class AskRequest(BaseModel):
    question: str
    scope: Literal["rules", "projects"] = "rules"


class RatingRequest(BaseModel):
    rating: Literal[-1, 0, 1]


# --- Endpoints --------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "ollama": llm.is_available()}


@app.post("/api/ask")
def ask(req: AskRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(422, "Please type a question.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            422, f"Your question is too long. Please keep it under {MAX_QUESTION_LENGTH} characters."
        )
    if req.scope == "projects":
        raise HTTPException(422, "Searching past projects is not available yet.")

    result = answer_rules(question)
    result["question_id"] = log_question(question, req.scope, result)
    return result


@app.post("/api/questions/{question_id}/rating")
def rate(question_id: int, req: RatingRequest):
    conn = state["conn"]
    cursor = conn.execute(
        "UPDATE questions SET rating = ? WHERE id = ?", (req.rating, question_id)
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(404, "Question not found.")
    return {"ok": True}


@app.get("/api/stats")
def stats():
    """What HR needs to see: what people ask, and where the policies fall short.

    Only 'rules' questions count: project questions are not HR's concern.
    """
    conn = state["conn"]

    def rows(sql: str) -> list[dict]:
        return [dict(r) for r in conn.execute(sql).fetchall()]

    totals = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(found), 0) AS answered "
        "FROM questions WHERE scope = 'rules'"
    ).fetchone()
    total, answered = totals["total"], totals["answered"]

    return {
        "total": total,
        "answered_pct": round(100 * answered / total) if total else 0,
        "unanswered_count": total - answered,
        "top_questions": rows(
            # Same question typed differently (case, spaces) counts as one.
            "SELECT MIN(text) AS text, COUNT(*) AS count, MAX(found) AS found "
            "FROM questions WHERE scope = 'rules' "
            "GROUP BY LOWER(TRIM(text)) ORDER BY count DESC, MAX(id) DESC LIMIT 10"
        ),
        "unanswered": rows(
            # Grouped, so a gap that many people hit stands out.
            "SELECT MIN(text) AS text, COUNT(*) AS count, MAX(created_at) AS last_asked "
            "FROM questions WHERE scope = 'rules' AND found = 0 "
            "GROUP BY LOWER(TRIM(text)) ORDER BY count DESC, MAX(id) DESC LIMIT 50"
        ),
        "thumbs_down": rows(
            "SELECT id, text, answer, created_at FROM questions "
            "WHERE scope = 'rules' AND rating = -1 ORDER BY id DESC LIMIT 50"
        ),
    }


# --- Answer pipeline ---------------------------------------------------------

def answer_rules(question: str) -> dict:
    """Search the policies, then let the AI write the answer if it is available.

    1. BM25 finds the top sections.
    2. Nothing relevant -> fixed "ask HR" message (never invent).
    3. AI available -> short answer written only from those sections.
    4. AI offline (or it fails) -> show the best section as-is.
    """
    index = state["rules_index"]
    results = index.search(question, k=TOP_K)

    if not index.is_relevant(question, results):
        return {"answer": RULES_NOT_FOUND, "sources": [], "mode": "search", "found": False}

    # Keep only sections nearly as relevant as the best one: weaker hits
    # (e.g. 'Approved suppliers' for a lost laptop) only add noise.
    best_score = results[0][1]
    chunks = [chunk for chunk, score in results if score >= best_score * SOURCE_RATIO]
    sources = [
        {"doc": c["doc"], "section": c["section"], "snippet": c["text"]} for c in chunks
    ]

    if llm.is_available():
        text = llm.answer(question, chunks)
        if text == llm.NOT_FOUND:
            return {"answer": RULES_NOT_FOUND, "sources": [], "mode": "ai", "found": False}
        if text:
            return {"answer": text, "sources": sources, "mode": "ai", "found": True}

    # Fallback mode: the best-matching section, word for word.
    return {"answer": chunks[0]["text"], "sources": sources, "mode": "search", "found": True}


def log_question(question: str, scope: str, result: dict) -> int:
    conn = state["conn"]
    cursor = conn.execute(
        "INSERT INTO questions (text, scope, answer, found, mode) VALUES (?, ?, ?, ?, ?)",
        (question, scope, result["answer"], int(result["found"]), result["mode"]),
    )
    conn.commit()
    return cursor.lastrowid
