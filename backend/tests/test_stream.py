"""The streaming endpoint and the 'local AI' metadata."""
import json

import pytest
from fastapi.testclient import TestClient

from app import db, llm, main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(main.app) as c:
        yield c


def events(response) -> list[tuple[str, dict]]:
    """Parse a Server-Sent Events body into (event, data) pairs."""
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def stream(client, question, scope="rules"):
    return client.post("/api/ask/stream", json={"question": question, "scope": scope})


def test_health_has_model(client):
    body = client.get("/api/health").json()
    assert body["model"] == llm.OLLAMA_MODEL
    assert isinstance(body["ollama"], bool)


def test_ask_has_latency_and_model(client, monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: False)
    body = client.post("/api/ask", json={"question": "Can I work from home?"}).json()
    assert body["mode"] == "search" and body["model"] is None
    assert body["ai_available"] is False
    assert isinstance(body["latency_ms"], int)


def test_stream_with_ai(client, monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(
        llm, "stream_answer",
        lambda q, chunks, prompt: iter(["You get ", "20 days. ", "[leeve.md › Annual leave]"]),
    )
    evts = events(stream(client, "How many days of annual leave do I get?"))
    names = [e for e, _ in evts]
    assert names == ["sources", "token", "token", "token", "done"]
    assert evts[0][1]["ai"] is True and evts[0][1]["sources"][0]["section"] == "Annual leave"
    done = evts[-1][1]
    assert done["mode"] == "ai" and done["model"] == llm.OLLAMA_MODEL
    # The final answer is checked like any other: wrong file name in the citation fixed.
    assert done["answer"] == "You get 20 days. [leave.md › Annual leave]"
    assert isinstance(done["question_id"], int)


def test_stream_ai_fails_midway_falls_back(client, monkeypatch):
    def broken(q, chunks, prompt):
        yield "You get"
        raise llm.AIUnavailable("connection lost")

    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "stream_answer", broken)
    done = events(stream(client, "What's the mileage rate?"))[-1][1]
    assert done["mode"] == "search"
    assert done["answer"].startswith("Business kilometres driven")


def test_stream_without_ai_has_no_tokens(client, monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: False)
    evts = events(stream(client, "footbridge", scope="projects"))
    assert [e for e, _ in evts] == ["sources", "done"]
    assert evts[0][1]["ai"] is False
    assert evts[-1][1]["projects"]


def test_stream_not_found(client, monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    evts = events(stream(client, "pizza recipe"))
    assert evts[0][1] == {"sources": [], "projects": [], "found": False, "ai": False, "model": llm.OLLAMA_MODEL}
    assert evts[-1][1]["found"] is False


def test_stream_validation_is_plain_json(client):
    response = stream(client, "  ")
    assert response.status_code == 422
    assert response.json()["detail"] == "Please type a question."
