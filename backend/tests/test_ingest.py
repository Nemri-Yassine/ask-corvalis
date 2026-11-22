from app import db
from app.ingest import get_chunks, load_all_docs, reload_docs


def test_every_doc_is_split_by_section():
    chunks = load_all_docs()
    docs = {c["doc"] for c in chunks}
    assert docs == {"expenses.md", "it-security.md", "leave.md", "onboarding.md", "purchasing.md"}
    assert len(chunks) == 21
    leave = [c["section"] for c in chunks if c["doc"] == "leave.md"]
    assert leave == ["Annual leave", "Sick leave", "Public holidays", "Remote work"]


def test_chunk_text_is_joined_into_one_paragraph():
    annual = next(c for c in load_all_docs() if c["section"] == "Annual leave")
    assert annual["text"].startswith("Full-time employees are entitled to 20 days")
    assert "\n" not in annual["text"]


def test_reload_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    assert reload_docs(conn) == 21
    assert reload_docs(conn) == 21             # second run replaces, no duplicates
    assert len(get_chunks(conn)) == 21


def test_document_title_is_kept():
    approval = next(c for c in load_all_docs() if c["section"] == "Approval")
    assert approval["title"] == "Expense policy"


def test_data_survives_reconnect(tmp_path):
    path = tmp_path / "test.db"
    conn = db.connect(path)
    reload_docs(conn)
    conn.close()
    assert len(get_chunks(db.connect(path))) == 21
