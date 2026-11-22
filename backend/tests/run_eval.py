"""Evaluation: run every question in eval_questions.json through the real API,
once with the local AI on and once with it off, check the answers, write a report.

    cd backend
    python tests/run_eval.py --label before      # Ollama must be running for "AI on"
    ... fix things ...
    python tests/run_eval.py --label after       # the report then shows before -> after

The API runs in-process (FastAPI TestClient) against a temporary database, so
the evaluation doesn't fill the HR dashboard. "AI off" is simulated by telling
the app Ollama is unavailable; "AI on" talks to the real Ollama model.

Writes, next to this file:
  eval_report.md          summary, results by category, per-question table
  eval_answers.md         every answer in full, for reading by a human
  eval_summary_<label>.json   headline numbers (used for before -> after)
"""
import argparse
import json
import re
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # so "import app" works when run as a script

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, llm, main  # noqa: E402

QUESTIONS = HERE / "eval_questions.json"


# --- Checks -------------------------------------------------------------------

def norm(text: str) -> str:
    """Lowercase, '2,500' -> '2500', curly quotes -> straight."""
    text = re.sub(r"(?<=\d),(?=\d)", "", text.lower())
    return text.replace("’", "'")


def numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", norm(text)))


def as_list(value) -> list:
    return [] if value is None else value if isinstance(value, list) else [value]


def retrieval_hit(q: dict, body: dict) -> bool | None:
    """Did the expected document/section (or project) come back? None = nothing expected."""
    docs = as_list(q["expected_doc"])
    if not docs:
        return None
    if q["scope"] == "projects":
        return any(p["number"] in docs for p in body.get("projects", []))
    sections = as_list(q["expected_section"])
    return any(
        s["doc"] in docs and (not sections or s["section"] in sections) for s in body.get("sources", [])
    )


def contains(text: str, phrase: str) -> bool:
    """Whole-word match, so the fact '2' is not found inside '2500'."""
    return re.search(rf"(?<!\w){re.escape(norm(phrase))}(?!\w)", text) is not None


def missing_facts(q: dict, answer: str) -> list[str]:
    """Expected facts not found in the answer ('a|b' = either is fine)."""
    text = norm(answer)
    return [f for f in q["expected_facts"] if not any(contains(text, alt) for alt in f.split("|"))]


def extra_numbers(question: str, body: dict) -> list[str]:
    """Simple hallucination check: numbers in the answer that appear neither in
    the sources nor in the question."""
    allowed = numbers_in(question) | numbers_in(json.dumps(body.get("sources", []), ensure_ascii=False))
    allowed |= numbers_in(json.dumps(body.get("projects", []), ensure_ascii=False))
    return sorted(numbers_in(body.get("answer", "")) - allowed)


def has_citation(q: dict, body: dict) -> bool | None:
    """Rules answers must point to their source: an inline [doc › section] for AI
    answers, the source list for search answers. None when not applicable."""
    if q["scope"] != "rules" or not body.get("found"):
        return None
    if body["mode"] == "ai":
        return bool(re.search(r"\[[^\]]+ › [^\]]+\]", body["answer"]))
    return bool(body.get("sources"))


def judge(q: dict, status: int, body: dict) -> dict:
    """All checks for one question, plus an overall pass/fail and a short note."""
    if "expect_status" in q:
        ok = status == q["expect_status"]
        return {"pass": ok, "note": f"HTTP {status}"}

    answer = body.get("answer", "")
    found = body.get("found", False)
    hit = retrieval_hit(q, body)
    missing = missing_facts(q, answer) if found else q["expected_facts"]
    # Only AI-written text can invent numbers; search answers are the source text itself.
    extras = extra_numbers(q["question"], body) if found and body.get("mode") == "ai" else []
    forbidden = [w for w in q.get("must_not_contain", []) if w.lower() in answer.lower()]
    wrong_projects = [p["number"] for p in body.get("projects", []) if p["number"] in q.get("must_not_return", [])]

    notes = []
    if q["should_answer"]:
        ok = found and hit is not False and not missing and not forbidden and not wrong_projects
        if not found:
            notes.append("refused (should answer)")
        elif hit is False:
            notes.append("wrong source")
        if found and missing:
            notes.append("missing: " + ", ".join(missing))
    else:
        ok = not found and not forbidden
        if found:
            notes.append("answered (should refuse)")
    if forbidden:
        notes.append("forbidden: " + ", ".join(forbidden))
    if wrong_projects:
        notes.append("should not list: " + ", ".join(wrong_projects))
    if extras:
        notes.append("numbers not in sources: " + ", ".join(extras))

    return {
        "pass": ok,
        "retrieval_hit": hit,
        "facts_ok": not missing,
        "citation": has_citation(q, body),
        "hallucinated_numbers": extras,
        "note": "; ".join(notes),
    }


# --- Running -------------------------------------------------------------------

def run(client: TestClient, questions: list[dict], mode: str) -> list[dict]:
    real_is_available = llm.is_available
    if mode == "off":
        llm.is_available = lambda: False
    else:
        llm._last_check["time"] = 0  # fresh check
        if not llm.is_available():
            print("!! Ollama is not running: skipping the 'AI on' run.")
            return []
        # Load the model into memory first, so the first question isn't timed
        # on a cold start (a 7B model can take >30 s to load).
        httpx.post(f"{llm.OLLAMA_URL}/api/generate", json={"model": llm.OLLAMA_MODEL, "prompt": "hi"}, timeout=180)
    rows = []
    try:
        for i, q in enumerate(questions, 1):
            question = "a" * 501 if q["question"] == "LONG_TEXT_501" else q["question"]
            payload = {"question": question, "scope": q["scope"]}
            response = client.post("/api/ask", json=payload)
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            result = judge(q, response.status_code, body)
            rows.append({
                "id": q["id"], "mode_requested": mode, "status": response.status_code,
                "answer": body.get("answer", body.get("detail", "")), "mode": body.get("mode"),
                "found": body.get("found"), "latency_ms": body.get("latency_ms"),
                "sources": [f"{s['doc']} › {s['section']}" for s in body.get("sources", [])],
                "projects": [p["number"] for p in body.get("projects", [])],
                **result,
            })
            print(f"[{mode}] {i:3}/{len(questions)} {'PASS' if result['pass'] else 'FAIL'} {q['id']}")
    finally:
        llm.is_available = real_is_available
    return rows


# --- Report --------------------------------------------------------------------

def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}% ({part}/{whole})" if whole else "–"


def summarize(questions: list[dict], rows: list[dict]) -> dict:
    by_id = {q["id"]: q for q in questions}
    answerable = [r for r in rows if by_id[r["id"]]["should_answer"] and "expect_status" not in by_id[r["id"]]]
    refusals = [r for r in rows if not by_id[r["id"]]["should_answer"] and "expect_status" not in by_id[r["id"]]]
    with_expected = [r for r in rows if r.get("retrieval_hit") is not None]
    cited = [r for r in rows if r.get("citation") is not None]
    latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    ai_latencies = [r["latency_ms"] for r in rows if r["mode"] == "ai"]
    return {
        "n": len(rows),
        "overall": [sum(r["pass"] for r in rows), len(rows)],
        "retrieval": [sum(bool(r["retrieval_hit"]) for r in with_expected), len(with_expected)],
        "answer": [sum(r["pass"] for r in answerable), len(answerable)],
        "refusal": [sum(r["pass"] for r in refusals), len(refusals)],
        "citation": [sum(bool(r["citation"]) for r in cited), len(cited)],
        "hallucinations": sum(bool(r.get("hallucinated_numbers")) for r in rows),
        "ai_answers": len(ai_latencies),
        "latency_avg": round(statistics.mean(latencies)) if latencies else None,
        "latency_p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))]) if latencies else None,
    }


def summary_rows(s: dict) -> list[tuple[str, str]]:
    return [
        ("Overall pass", pct(*s["overall"])),
        ("Retrieval accuracy (expected source returned)", pct(*s["retrieval"])),
        ("Answer accuracy (should answer: right source + facts)", pct(*s["answer"])),
        ("Refusal accuracy (should say it doesn't know)", pct(*s["refusal"])),
        ("Citation present (answered rules questions)", pct(*s["citation"])),
        ("Answers with numbers not in the sources", str(s["hallucinations"])),
        ("Answers written by the AI", str(s["ai_answers"])),
        ("Latency avg / p95", f"{s['latency_avg']} ms / {s['latency_p95']} ms" if s["latency_avg"] is not None else "–"),
    ]


def write_report(questions, results, label):
    by_id = {q["id"]: q for q in questions}
    modes = [m for m in ("on", "off") if results.get(m)]
    summaries = {m: summarize(questions, results[m]) for m in modes}
    (HERE / f"eval_summary_{label}.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")

    title = {"on": "AI on", "off": "AI off"}
    out = [f"# Evaluation report ({label})", "",
           f"{len(questions)} questions, run through `/api/ask` with the local AI "
           f"({llm.OLLAMA_MODEL}) on and off. Generated by `tests/run_eval.py`; "
           "questions and expected answers in `tests/eval_questions.json`.", "",
           "## Summary", "",
           "| Metric | " + " | ".join(title[m] for m in modes) + " |",
           "|---|" + "---|" * len(modes)]
    labels = [name for name, _ in summary_rows(summaries[modes[0]])]
    values = {m: dict(summary_rows(summaries[m])) for m in modes}
    out += [f"| {name} | " + " | ".join(values[m][name] for m in modes) + " |" for name in labels]

    before_file = HERE / "eval_summary_before.json"
    if label != "before" and before_file.exists():
        before = json.loads(before_file.read_text(encoding="utf-8"))
        out += ["", "## Before → after fixes", "",
                "| Metric | " + " | ".join(f"{title[m]}: before → after" for m in modes) + " |",
                "|---|" + "---|" * len(modes)]
        old = {m: dict(summary_rows(before[m])) for m in modes if m in before}
        out += [f"| {name} | " + " | ".join(
            f"{old[m][name]} → {values[m][name]}" if m in old else values[m][name] for m in modes
        ) + " |" for name in labels]

    out += ["", "## By category", "", "| Category | n | " + " | ".join(title[m] for m in modes) + " |",
            "|---|---|" + "---|" * len(modes)]
    categories = list(dict.fromkeys(q["category"] for q in questions))
    for c in categories:
        cells = []
        for m in modes:
            rows = [r for r in results[m] if by_id[r["id"]]["category"] == c]
            cells.append(pct(sum(r["pass"] for r in rows), len(rows)))
        n = sum(1 for q in questions if q["category"] == c)
        out.append(f"| {c} | {n} | " + " | ".join(cells) + " |")

    out += ["", "## Per question", "", "| ID | Category | Question | " + " | ".join(title[m] for m in modes) + " | Notes |",
            "|---|---|---|" + "---|" * len(modes) + "---|"]
    rows_by = {m: {r["id"]: r for r in results[m]} for m in modes}
    for q in questions:
        cells, notes = [], []
        for m in modes:
            r = rows_by[m][q["id"]]
            cells.append(("✅" if r["pass"] else "❌") + f" {r['mode'] or r['status']}")
            if r["note"] and r["note"] not in notes:
                notes.append(f"{title[m]}: {r['note']}")
        question = q["question"] if q["question"] != "LONG_TEXT_501" else "(501 × 'a')"
        question = question.replace("|", "\\|").replace("<", "&lt;")[:70]
        out.append(f"| {q['id']} | {q['category']} | {question} | " + " | ".join(cells) + " | " + "<br>".join(notes) + " |")
    (HERE / "eval_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    answers = [f"# All answers ({label})", "", "Every answer in full, to read and judge by hand.", ""]
    for q in questions:
        question = q["question"] if q["question"] != "LONG_TEXT_501" else "(501 × 'a')"
        answers.append(f"## {q['id']} ({q['category']}): {question}")
        for m in modes:
            r = rows_by[m][q["id"]]
            answers.append(f"**{title[m]}** · {'✅' if r['pass'] else '❌'} · mode={r['mode']} found={r['found']} "
                           f"· {r['latency_ms']} ms · sources: {', '.join(r['sources'] or r['projects']) or '–'}")
            answers.append("")
            answers.append("> " + (r["answer"] or "").replace("\n", "\n> "))
            answers.append("")
    (HERE / "eval_answers.md").write_text("\n".join(answers) + "\n", encoding="utf-8")
    return summaries


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="latest", help="e.g. before / after")
    parser.add_argument("--modes", default="on,off", help="on,off | on | off")
    args = parser.parse_args()

    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / "eval.db"
        with TestClient(main.app) as client:
            results = {m: run(client, questions, m) for m in args.modes.split(",")}

    summaries = write_report(questions, results, args.label)
    for m, s in summaries.items():
        print(f"\n== AI {m} ==")
        for name, value in summary_rows(s):
            print(f"  {name:<55} {value}")


if __name__ == "__main__":
    main_cli()
