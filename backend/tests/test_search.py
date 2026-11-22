"""Search quality on the real policy documents.

These questions are also what MIN_SCORE / MIN_COVERAGE were tuned on.
"""
import pytest

from app.ingest import load_all_docs
from app.search import Index, chunk_text, tokenize


@pytest.fixture(scope="module")
def index():
    return Index(load_all_docs(), chunk_text)


def best(index, question):
    results = index.search(question)
    top = results[0][0]
    return f"{top['doc']} › {top['section']}", index.is_relevant(question, results)


# --- The three required checks -------------------------------------------

def test_annual_leave(index):
    assert best(index, "how many days of annual leave") == ("leave.md › Annual leave", True)


def test_mileage_rate(index):
    assert best(index, "mileage rate") == ("expenses.md › Mileage", True)


def test_pizza_recipe_not_found(index):
    results = index.search("pizza recipe")
    assert not index.is_relevant("pizza recipe", results)


# --- Wider coverage: one or more questions per document -------------------

@pytest.mark.parametrize("question, expected", [
    ("How many days of annual leave do I get?", "leave.md › Annual leave"),
    ("What's the mileage rate?", "expenses.md › Mileage"),
    ("I lost my laptop, what do I do?", "it-security.md › Lost or stolen devices"),
    ("Do I need a quote for a €3,000 purchase?", "purchasing.md › Quotes"),
    ("how long must my password be", "it-security.md › Passwords"),
    ("when do I need a medical certificate", "leave.md › Sick leave"),
    ("what if I'm sick", "leave.md › Sick leave"),
    ("can I work from home", "leave.md › Remote work"),
    ("who approves a 700 euro claim", "expenses.md › Approval"),
    ("can I take first class on the train", "expenses.md › Travel"),
    ("is alcohol reimbursed", "expenses.md › Meals"),
    ("can I install software", "it-security.md › Software installation"),
    ("do I need the VPN in a hotel", "it-security.md › VPN"),
    ("what happens on my first day", "onboarding.md › First day"),
    ("when is my probation review", "onboarding.md › Probation review"),
    ("how do I order a new screen", "purchasing.md › Approved suppliers"),
    ("do I need approval for a software subscription", "purchasing.md › Subscriptions"),
])
def test_finds_right_section(index, question, expected):
    assert best(index, question) == (expected, True)


@pytest.mark.parametrize("question", [
    "pizza recipe",
    "what is the weather tomorrow",
    "parental leave",              # shares only the word 'leave'
    "company car policy",          # shares only 'car' / 'policy'
    "what is the wifi password",   # shares only 'password'
    "can I bring my dog to the office",
    "hello",
    "",
])
def test_off_topic_not_found(index, question):
    assert not index.is_relevant(question, index.search(question))


def test_tokenize():
    assert tokenize("How many DAYS of leave?") == ["day", "leav"]
    assert tokenize("approves") == tokenize("approval") == tokenize("approved")
    assert tokenize("Liège") == tokenize("Liege") == ["lieg"]


def test_numbers_do_not_count_against_coverage(index):
    assert best(index, "Can I take a taxi at 11pm?") == ("expenses.md › Travel", True)
