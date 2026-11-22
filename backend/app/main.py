"""Ask Corvalis — API server."""
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import db, llm
from app.ingest import get_chunks, ingest_if_empty
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

# Filled at startup.
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    ingest_if_empty(conn)  # these two only do work on the very first start
    seed_if_empty(conn)
    state["conn"] = conn
    state["rules_index"] = Index(get_chunks(conn), chunk_text)
    state["projects_index"] = Index(get_projects(conn), project_text)
    yield
    conn.close()


app = FastAPI(title="Ask Corvalis", lifespan=lifespan)


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
        result = answer_projects(question, req.project_type, req.year_from, req.year_to)
    else:
        result = {**answer_rules(question), "projects": []}
    result["question_id"] = log_question(question, req.scope, result)
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

    chunks = strong_results(results)
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


def answer_projects(
    question: str, project_type: str | None, year_from: int | None, year_to: int | None
) -> dict:
    """Same pipeline as answer_rules, over past projects, with optional filters.

    The result also lists the matching projects in full, so the UI can show cards.
    """
    index = state["projects_index"]
    results = [
        (p, score)
        for p, score in index.search(question, k=None)  # rank all, then filter
        if (not project_type or p["type"] == project_type)
        and (not year_from or p["year"] >= year_from)
        and (not year_to or p["year"] <= year_to)
    ][:PROJECTS_TOP_K]

    not_found = {
        "answer": PROJECTS_NOT_FOUND, "sources": [], "projects": [], "mode": "search", "found": False
    }
    if not index.is_relevant(question, results, MIN_COVERAGE_PROJECTS):
        return not_found

    projects = strong_results(results)
    sources = [{"doc": p["number"], "section": p["title"], "snippet": p["summary"]} for p in projects]

    if llm.is_available():
        # Give the model each project as a "source" it can cite: [number › title].
        as_sources = [
            {
                "doc": p["number"],
                "section": p["title"],
                "text": f"{p['type']}, {p['city']}, {p['year']}. Project manager: "
                f"{p['project_manager']}. Materials: {p['materials']}. {p['summary']}",
            }
            for p in projects
        ]
        text = llm.answer(question, as_sources, system_prompt=llm.PROJECTS_PROMPT)
        if text == llm.NOT_FOUND:
            return {**not_found, "mode": "ai"}
        if text:
            text = llm.format_project_answer(text, projects)
        if text:
            return {"answer": text, "sources": sources, "projects": projects, "mode": "ai", "found": True}

    # Fallback mode: the project cards speak for themselves.
    count = len(projects)
    answer = f"Found {count} past project{'s' if count > 1 else ''} that match{'es' if count == 1 else ''}:"
    return {"answer": answer, "sources": sources, "projects": projects, "mode": "search", "found": True}


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
