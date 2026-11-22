"""Optional local AI model (Ollama).

The app must work without it: every function here fails safely and the
caller falls back to showing the search result.
"""
import os
import re
import time

import httpx

# 127.0.0.1 rather than localhost: on Windows 'localhost' tries IPv6 first (+2s per call).
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
TIMEOUT_SECONDS = 30

# The model replies with this exact word when the sources don't answer the question.
NOT_FOUND = "NOT_FOUND"

RULES_PROMPT = f"""You answer questions from Corvalis employees about internal company rules.
Use ONLY the sources below. Never use outside knowledge and never guess.
Answer in at most 4 short sentences, in plain English.
After each fact, cite its source exactly as written in the source header, e.g. [leave.md › Annual leave].
If the sources only partly answer the question, say what they do say.
If the sources say nothing about the question, reply with only the word: {NOT_FOUND}"""

PROJECTS_PROMPT = f"""You help Corvalis engineers find similar past projects.
Use ONLY the projects listed below. Never invent projects or details.
List only the projects that really match the question, most relevant first.
Write one line per project, exactly in this format, and nothing else:
2019-042: 60 m weathering-steel footbridge over the Sambre.
After the project number and colon, say in under 15 words why the project matches.
If none of the projects match, reply with only the word: {NOT_FOUND}"""

# A line that starts with a project number, in any of the shapes small models write:
#   "2019-042: reason"   "[2014-017] reason"   "[2016-023 › Title]"   "- 2014-017 (…): reason"
PROJECT_LINE = re.compile(r"^\W*(\d{4}-\d{3})(?:[^\]:]*[\]:])?\s*(.*)$")


def format_project_answer(text: str, projects: list[dict]) -> str | None:
    """Turn the model's reply into '- NUMBER (year, PM): reason' lines.

    Small models get names and years wrong, so those come from our data; the
    model only decides which projects match and why. Projects we did not give
    it are dropped. Returns None if nothing usable is left (caller falls back).
    """
    by_number = {p["number"]: p for p in projects}
    entries: list[list[str]] = []  # [number, reason]
    for line in text.splitlines():
        match = PROJECT_LINE.match(line)
        if match and match.group(1) in by_number:
            entries.append([match.group(1), match.group(2).strip()])
        elif entries and not entries[-1][1] and line.strip():
            entries[-1][1] = line.strip()  # reason written on the next line

    lines, seen = [], set()
    for number, reason in entries:
        if number in seen:
            continue
        seen.add(number)
        p = by_number[number]
        lines.append(f"- {number} ({p['year']}, {p['project_manager']}): {reason or p['title']}")
    return "\n".join(lines) or None

# Remember the result of the last ping for 30 seconds,
# so we don't ping Ollama on every question.
_CACHE_SECONDS = 30
_last_check = {"time": 0.0, "available": False}


def is_available() -> bool:
    """True if Ollama answers on /api/tags (result cached for 30s)."""
    now = time.time()
    if now - _last_check["time"] < _CACHE_SECONDS:
        return _last_check["available"]

    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        available = response.status_code == 200
    except httpx.HTTPError:
        available = False

    _last_check["time"] = now
    _last_check["available"] = available
    return available


def format_sources(chunks: list[dict]) -> str:
    return "\n\n".join(f"[{c['doc']} › {c['section']}]\n{c['text']}" for c in chunks)


def answer(question: str, chunks: list[dict], system_prompt: str = RULES_PROMPT) -> str | None:
    """Ask the model to answer from the given chunks.

    Returns the answer text, NOT_FOUND, or None if anything went wrong
    (Ollama down, too slow, bad reply) — the caller then falls back to search.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "options": {"temperature": 0},  # same question -> same answer
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Sources:\n\n{format_sources(chunks)}\n\nQuestion: {question}"},
        ],
    }
    try:
        response = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        text = response.json()["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, ValueError):
        # Treat Ollama as offline for the next 30s so we don't wait again.
        _last_check["time"] = time.time()
        _last_check["available"] = False
        return None

    # Small models sometimes write a sentence AND the marker: the marker wins
    # only if nothing else useful is left.
    text = text.replace(NOT_FOUND, "").strip()
    if not text:
        return NOT_FOUND
    return fix_citations(text, chunks)


CITATION = re.compile(r"\[([^\[\]]+?) › ([^\[\]]+?)\]")


def fix_citations(text: str, chunks: list[dict]) -> str:
    """Make sure every [doc › Section] citation points to a real source.

    Small models sometimes get the file name wrong: we correct it from the
    section title, and drop citations of sections we never gave the model.
    """
    doc_of_section = {c["section"].lower(): c["doc"] for c in chunks}

    def fix(match: re.Match) -> str:
        section = match.group(2).strip()
        doc = doc_of_section.get(section.lower())
        return f"[{doc} › {section}]" if doc else ""

    return CITATION.sub(fix, text).strip()
