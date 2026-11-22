"""Past projects (P9): sample data, search, and the /api/ask projects scope."""
import pytest
from fastapi.testclient import TestClient

from app import db, llm, main
from app.search import MIN_COVERAGE_PROJECTS, Index, project_text
from app.seed_projects import generate_projects, get_projects, seed_if_empty


# --- Sample data ---------------------------------------------------------------

def test_sixty_projects_same_every_time():
    projects = generate_projects()
    assert len(projects) == 60
    assert projects == generate_projects()  # fixed seed
    assert len({p["number"] for p in projects}) == 60
    assert all(2012 <= p["year"] <= 2026 for p in projects)
    assert all(p["folder_path"] == f"\\\\fileserver\\projects\\{p['number']}" for p in projects)


def test_footbridges_in_different_materials():
    footbridges = [p for p in generate_projects() if p["type"] == "footbridge"]
    assert len(footbridges) == 4
    assert len({p["materials"] for p in footbridges}) == 4


def test_seed_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    assert seed_if_empty(conn) == 60
    assert seed_if_empty(conn) == 0
    assert len(get_projects(conn)) == 60


# --- Search --------------------------------------------------------------------

@pytest.fixture(scope="module")
def index():
    return Index(generate_projects(), project_text)


def numbers(index, question, k=5):
    return [p["number"] for p, _ in index.search(question, k=k)]


def test_timber_footbridge(index):
    top_two = numbers(index, "Have we designed a timber footbridge before?", k=2)
    assert set(top_two) == {"2014-017", "2024-031"}  # the two timber footbridges


def test_city_without_accent(index):
    assert numbers(index, "hospital extension in Liege")[0] == "2020-012"


@pytest.mark.parametrize("question", ["swimming pool", "nuclear power plant", "tunnel"])
def test_unrelated_not_found(index, question):
    assert not index.is_relevant(question, index.search(question), MIN_COVERAGE_PROJECTS)


# --- API -----------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(llm, "is_available", lambda: False)
    with TestClient(main.app) as c:
        yield c


def ask(client, question, **filters):
    return client.post("/api/ask", json={"question": question, "scope": "projects", **filters}).json()


def test_ask_projects_fallback(client):
    body = ask(client, "Have we designed a timber footbridge before?")
    assert body["found"] is True and body["mode"] == "search"
    assert body["answer"].startswith("Found")
    assert body["projects"][0]["number"] in {"2014-017", "2024-031"}
    assert body["projects"][0]["folder_path"].startswith("\\\\fileserver\\projects\\")
    assert body["sources"][0]["doc"] == body["projects"][0]["number"]


def test_filters(client):
    body = ask(client, "footbridge", year_from=2020)
    assert {p["number"] for p in body["projects"]} == {"2022-008", "2024-031"}
    body = ask(client, "timber", project_type="footbridge", year_to=2015)
    assert [p["number"] for p in body["projects"]] == ["2014-017"]


def test_no_match(client):
    body = ask(client, "swimming pool")
    assert body["found"] is False
    assert body["answer"] == main.PROJECTS_NOT_FOUND
    assert body["projects"] == []


def test_project_questions_not_in_hr_stats(client):
    ask(client, "footbridge")
    assert client.get("/api/stats").json()["total"] == 0


def test_filter_choices(client):
    f = client.get("/api/projects/filters").json()
    assert "footbridge" in f["types"]
    assert f["min_year"] >= 2012 and f["max_year"] <= 2026


def test_ai_project_answer(client, monkeypatch):
    seen = {}

    def fake_answer(question, chunks, system_prompt):
        seen["prompt"], seen["chunks"] = system_prompt, chunks
        return "2014-017 (2014, Marc Renard): timber arch. [2014-017 › Ourthe valley timber footbridge]"

    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "answer", fake_answer)
    body = ask(client, "timber footbridge")
    assert body["mode"] == "ai"
    assert seen["prompt"] == llm.PROJECTS_PROMPT
    # The model gets the PM and year, so it can list them.
    assert any("Project manager: Marc Renard" in c["text"] for c in seen["chunks"])
