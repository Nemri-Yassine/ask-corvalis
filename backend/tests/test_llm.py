from app import llm

CHUNKS = [
    {"doc": "it-security.md", "section": "Lost or stolen devices", "text": "..."},
    {"doc": "leave.md", "section": "Annual leave", "text": "..."},
]


def test_wrong_doc_name_is_corrected():
    text = "Call the IT desk. [leave.md › Lost or stolen devices]"
    assert llm.fix_citations(text, CHUNKS) == "Call the IT desk. [it-security.md › Lost or stolen devices]"


def test_unknown_section_citation_is_dropped():
    assert llm.fix_citations("Yes. [hr.md › Bonuses]", CHUNKS) == "Yes."


def test_correct_citation_untouched():
    text = "20 days. [leave.md › Annual leave]"
    assert llm.fix_citations(text, CHUNKS) == text


def test_offline_returns_none(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens here
    assert llm.answer("anything", CHUNKS) is None
    assert llm.is_available() is False  # marked offline after the failure
