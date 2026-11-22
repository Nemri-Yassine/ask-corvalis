"""Key retrieval and refusal checks from the evaluation (tests/run_eval.py),
kept as fast tests so they stay green. Search only: no AI needed.

eval_questions.json is the set the fixes were tuned on; eval_holdout.json was
written before the fixes and never tuned on, to catch overfitting.
"""
import json
from pathlib import Path

import pytest

from app.ingest import load_all_docs
from app.search import Index, chunk_text

HERE = Path(__file__).parent
INDEX = Index(load_all_docs(), chunk_text)


def load(name):
    return [q for q in json.loads((HERE / name).read_text(encoding="utf-8"))
            if q["scope"] == "rules" and "expect_status" not in q]


def as_list(v):
    return v if isinstance(v, list) else [v]


def right_answer_found(q) -> bool:
    results = INDEX.search(q["question"])
    return INDEX.is_relevant(q["question"], results) and any(
        c["doc"] in as_list(q["expected_doc"]) and c["section"] in as_list(q["expected_section"])
        for c, _ in results
    )


def refused(q) -> bool:
    return not INDEX.is_relevant(q["question"], INDEX.search(q["question"]))


def rate(questions, check):
    return sum(check(q) for q in questions) / len(questions)


EVAL, HOLDOUT = load("eval_questions.json"), load("eval_holdout.json")


def test_retrieval_rate_eval_set():
    answerable = [q for q in EVAL if q["should_answer"]]
    assert rate(answerable, right_answer_found) >= 0.70  # 0.49 before the fixes


def test_retrieval_rate_holdout_set():
    answerable = [q for q in HOLDOUT if q["should_answer"]]
    assert rate(answerable, right_answer_found) >= 0.65


@pytest.mark.parametrize("q", [q for q in EVAL if q["category"] == "direct"], ids=lambda q: q["id"])
def test_direct_questions(q):
    # Known misses (see WEAKNESSES.md): plain words shared by many sections.
    if q["id"] in {"ob-buddy-1"}:
        pytest.xfail("only 1 of 3 keywords is in the Buddy section")
    assert right_answer_found(q)


@pytest.mark.parametrize(
    "q",
    [q for q in EVAL + HOLDOUT if q["category"] in ("off_topic", "not_covered", "holdout_refuse")],
    ids=lambda q: q["id"],
)
def test_refuses_what_policies_do_not_cover(q):
    if q["id"] == "nc-6":
        pytest.xfail("'working' matches the title 'Leave and working time' (see WEAKNESSES.md)")
    assert refused(q)
