"""API tests. Ollama is replaced by fakes, so these run without it."""
import pytest
from fastapi.testclient import TestClient

from app import db, llm, main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def ai_off(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: False)


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(
        llm, "answer", lambda q, chunks, **kw: "You get 20 days. [leave.md › Annual leave]"
    )


def ask(client, question, scope="rules"):
    return client.post("/api/ask", json={"question": question, "scope": scope})


def test_fallback_returns_section_verbatim(client, ai_off):
    body = ask(client, "How many days of annual leave do I get?").json()
    assert body["mode"] == "search"
    assert body["found"] is True
    assert body["answer"].startswith("Full-time employees are entitled to 20 days")
    assert body["sources"][0] == {
        "doc": "leave.md", "section": "Annual leave", "snippet": body["answer"]
    }
    assert isinstance(body["question_id"], int)


def test_ai_answer(client, ai_on):
    body = ask(client, "How many days of annual leave do I get?").json()
    assert body["mode"] == "ai"
    assert body["found"] is True
    assert "[leave.md › Annual leave]" in body["answer"]
    assert body["sources"][0]["section"] == "Annual leave"


def test_ai_failure_falls_back_to_search(client, monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "answer", lambda q, chunks, **kw: None)  # e.g. timeout
    body = ask(client, "What's the mileage rate?").json()
    assert body["mode"] == "search"
    assert body["sources"][0]["section"] == "Mileage"


def test_ai_says_not_in_sources(client, monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "answer", lambda q, chunks, **kw: llm.NOT_FOUND)
    body = ask(client, "What's the mileage rate?").json()
    assert body["found"] is False
    assert body["answer"] == main.RULES_NOT_FOUND


@pytest.mark.parametrize("question", ["pizza recipe", "parental leave"])
def test_off_topic_says_ask_hr(client, ai_on, question):
    body = ask(client, question).json()
    assert body["found"] is False
    assert body["answer"] == main.RULES_NOT_FOUND
    assert body["sources"] == []


@pytest.mark.parametrize("question, message", [
    ("", "Please type a question."),
    ("   ", "Please type a question."),
    ("x" * 501, "Your question is too long. Please keep it under 500 characters."),
])
def test_validation(client, question, message):
    response = ask(client, question)
    assert response.status_code == 422
    assert response.json()["detail"] == message


def test_questions_are_logged_and_rated(client, ai_off):
    qid = ask(client, "Can I work from home?").json()["question_id"]
    assert client.post(f"/api/questions/{qid}/rating", json={"rating": -1}).status_code == 200
    row = main.state["conn"].execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    assert row["text"] == "Can I work from home?"
    assert row["found"] == 1 and row["mode"] == "search" and row["rating"] == -1


def test_rating_errors(client):
    assert client.post("/api/questions/999/rating", json={"rating": 1}).status_code == 404
    assert client.post("/api/questions/1/rating", json={"rating": 5}).status_code == 422


def test_weak_sources_are_dropped(client, ai_off):
    body = ask(client, "I lost my laptop, what do I do?").json()
    assert [s["section"] for s in body["sources"]] == ["Lost or stolen devices"]
