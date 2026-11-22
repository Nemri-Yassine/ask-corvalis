"""Ask Corvalis — API server."""
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app import db, llm
from app.ingest import get_chunks, reload_docs
from app.search import MIN_COVERAGE_PROJECTS, Index, chunk_text, project_text
from app.seed_projects import get_projects, seed_if_empty

MAX_QUESTION_LENGTH = 500
TOP_K = 3
SOURCE_RATIO = 0.5  # a source is shown if it scores at least half the best one
RULES_NOT_FOUND = (
    "I couldn't find this in the Corvalis policies. Please ask HR (hr@corvalis.be)."
)
PROJECTS_TOP_K = 5
PROJECTS_NOT_FOUND = (
    "I couldn't find a past project that matches. Try other words: a building type, "
    "a material or a city."
)

logger = logging.getLogger("ask-corvalis")

# Filled at startup.
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    reload_docs(conn)  # policies: always re-read from docs/ (picks up edits)
    seed_if_empty(conn)  # sample projects: only on the very first start
    state["conn"] = conn
    state["rules_index"] = Index(get_chunks(conn), chunk_text)
    state["projects_index"] = Index(get_projects(conn), project_text)
    yield
    conn.close()


app = FastAPI(title="Ask Corvalis", lifespan=lifespan)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    """Any bug: log it, and give the UI a message it can show (instead of plain text)."""
    logger.exception("Unexpected error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong, try again."})


# --- Request / response shapes ----------------------------------------------

class AskRequest(BaseModel):
    question: str
    scope: Literal["rules", "projects"] = "rules"
    # Optional filters, only used for past projects.
    project_type: str | None = None
    year_from: int | None = None
    year_to: int | None = None


class RatingRequest(BaseModel):
    rating: Literal[-1, 0, 1]


# --- Endpoints --------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "ollama": llm.is_available(), "model": llm.OLLAMA_MODEL}


def clean_question(req: AskRequest) -> str:
    question = req.question.strip()
    if not question:
        raise HTTPException(422, "Please type a question.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            422, f"Your question is too long. Please keep it under {MAX_QUESTION_LENGTH} characters."
        )
    return question


@app.post("/api/ask")
def ask(req: AskRequest):
    """The whole answer in one response."""
    question = clean_question(req)
    start = time.perf_counter()
    if req.scope == "projects":
        result = answer_projects(question, req.project_type, req.year_from, req.year_to)
    else:
        result = answer_rules(question)
    return complete(result, question, req.scope, start)


@app.post("/api/ask/stream")
def ask_stream(req: AskRequest):
    """Same answer, sent as Server-Sent Events while it is being written:

    event: sources  -> what was found, and whether the local AI will write the answer
    event: token    -> one piece of the AI's text (many of these)
    event: done     -> the final, checked answer + metadata (same shape as /api/ask)
    """
    question = clean_question(req)  # validation errors are normal JSON 422s

    def events():
        try:
            start = time.perf_counter()
            r = retrieve(question, req)
            use_ai = r["found"] and llm.is_available()
            yield sse("sources", {
                "sources": r["sources"], "projects": r["projects"], "found": r["found"],
                "ai": use_ai, "model": llm.OLLAMA_MODEL,
            })

            ai_text = None
            if use_ai:
                pieces = []
                try:
                    for piece in llm.stream_answer(question, r["llm_sources"], r["prompt"]):
                        pieces.append(piece)
                        yield sse("token", {"text": piece})
                    ai_text = llm.clean_reply("".join(pieces), r["llm_sources"])
                except llm.AIUnavailable:
                    ai_text = None  # finish() falls back to the search result

            yield sse("done", complete(finish(r, ai_text), question, req.scope, start))
        except Exception:
            logger.exception("Unexpected error while streaming")
            yield sse("error", {"detail": "Something went wrong, try again."})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def sse(event: str, data: dict) -> str:
    """One Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def complete(result: dict, question: str, scope: str, start: float) -> dict:
    """Log the question and add the metadata the UI shows under the answer."""
    result["question_id"] = log_question(question, scope, result)
    result["model"] = llm.OLLAMA_MODEL if result["mode"] == "ai" else None
    result["ai_available"] = llm.is_available()
    result["latency_ms"] = round((time.perf_counter() - start) * 1000)
    return result


@app.get("/api/projects/filters")
def project_filters():
    """Choices for the filter controls in the UI."""
    conn = state["conn"]
    types = [r[0] for r in conn.execute("SELECT DISTINCT type FROM projects ORDER BY type")]
    years = conn.execute("SELECT MIN(year), MAX(year) FROM projects").fetchone()
    return {"types": types, "min_year": years[0], "max_year": years[1]}


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

# Every answer goes through the same three steps:
#   1. retrieve()  BM25 search + "relevant enough?" rule  (no AI)
#   2. the local AI writes an answer from what was found  (if Ollama is up)
#   3. finish()    checks the AI's text, or falls back to the search result
# /api/ask runs them in one go; /api/ask/stream sends the AI's text as it comes.

def answer_rules(question: str) -> dict:
    return finish(*with_ai(question, retrieve_rules(question)))


def answer_projects(
    question: str, project_type: str | None, year_from: int | None, year_to: int | None
) -> dict:
    return finish(*with_ai(question, retrieve_projects(question, project_type, year_from, year_to)))


def with_ai(question: str, r: dict) -> tuple[dict, str | None]:
    """Step 2, in one go (the streaming endpoint does this piece by piece)."""
    if r["found"] and llm.is_available():
        return r, llm.answer(question, r["llm_sources"], system_prompt=r["prompt"])
    return r, None


def retrieve(question: str, req: AskRequest) -> dict:
    if req.scope == "projects":
        return retrieve_projects(question, req.project_type, req.year_from, req.year_to)
    return retrieve_rules(question)


def retrieve_rules(question: str) -> dict:
    """Step 1 for company rules: the policy sections that answer the question."""
    index = state["rules_index"]
    results = index.search(question, k=TOP_K)
    r = {"found": False, "sources": [], "projects": [], "not_found": RULES_NOT_FOUND}
    if not index.is_relevant(question, results):
        return r

    chunks = strong_results(results)
    return {
        **r,
        "found": True,
        "sources": [{"doc": c["doc"], "section": c["section"], "snippet": c["text"]} for c in chunks],
        "llm_sources": chunks,
        "prompt": llm.RULES_PROMPT,
        # Without AI: the best-matching section, word for word.
        "fallback": chunks[0]["text"],
    }


def retrieve_projects(
    question: str, project_type: str | None, year_from: int | None, year_to: int | None
) -> dict:
    """Step 1 for past projects, with the optional filters."""
    index = state["projects_index"]
    results = [
        (p, score)
        for p, score in index.search(question, k=None)  # rank all, then filter
        if (not project_type or p["type"] == project_type)
        and (not year_from or p["year"] >= year_from)
        and (not year_to or p["year"] <= year_to)
    ][:PROJECTS_TOP_K]
    r = {"found": False, "sources": [], "projects": [], "not_found": PROJECTS_NOT_FOUND}
    if not index.is_relevant(question, results, MIN_COVERAGE_PROJECTS):
        return r

    projects = strong_results(results)
    count = len(projects)
    return {
        **r,
        "found": True,
        "sources": [{"doc": p["number"], "section": p["title"], "snippet": p["summary"]} for p in projects],
        "projects": projects,
        # Give the model each project as a "source" it can cite: [number › title].
        "llm_sources": [
            {
                "doc": p["number"],
                "section": p["title"],
                "text": f"{p['type']}, {p['city']}, {p['year']}. Project manager: "
                f"{p['project_manager']}. Materials: {p['materials']}. {p['summary']}",
            }
            for p in projects
        ],
        "prompt": llm.PROJECTS_PROMPT,
        # Without AI: the project cards speak for themselves.
        "fallback": f"Found {count} past project{'s' if count > 1 else ''} "
        f"that match{'es' if count == 1 else ''}:",
    }


def finish(r: dict, ai_text: str | None) -> dict:
    """Step 3: turn the search result + the AI's (checked) text into the answer."""
    base = {"sources": r["sources"], "projects": r["projects"]}
    not_found = {"answer": r["not_found"], "sources": [], "projects": [], "found": False}

    if not r["found"]:
        return {**not_found, "mode": "search"}
    if ai_text == llm.NOT_FOUND:  # the AI read the sources and they don't answer it
        return {**not_found, "mode": "ai"}
    if ai_text and r["projects"]:
        # Project numbers, years and PMs come from our data, not from the model.
        ai_text = llm.format_project_answer(ai_text, r["projects"])
    elif ai_text and not llm.CITATION.search(ai_text):
        # The small model sometimes forgets to cite: add the sources it was given.
        ai_text += " " + " ".join(f"[{s['doc']} › {s['section']}]" for s in r["sources"])
    if ai_text:
        return {**base, "answer": ai_text, "mode": "ai", "found": True}
    # AI offline, failed, or gave nothing usable.
    return {**base, "answer": r["fallback"], "mode": "search", "found": True}


def strong_results(results: list[tuple[dict, float]]) -> list[dict]:
    """Keep only results nearly as relevant as the best one: weaker hits
    (e.g. 'Approved suppliers' for a lost laptop) only add noise."""
    best_score = results[0][1]
    return [item for item, score in results if score >= best_score * SOURCE_RATIO]


def log_question(question: str, scope: str, result: dict) -> int:
    conn = state["conn"]
    cursor = conn.execute(
        "INSERT INTO questions (text, scope, answer, found, mode) VALUES (?, ?, ?, ?, ?)",
        (question, scope, result["answer"], int(result["found"]), result["mode"]),
    )
    conn.commit()
    return cursor.lastrowid
