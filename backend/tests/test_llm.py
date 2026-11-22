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


PROJECTS = [
    {"number": "2014-017", "year": 2014, "project_manager": "Marc Renard", "title": "Ourthe footbridge"},
    {"number": "2016-023", "year": 2016, "project_manager": "Thomas Dubois", "title": "Car park"},
]


def test_project_answer_formats_from_our_data():
    raw = (
        "2014-017: timber arch footbridge.\n"
        "[2016-023 › Car park] \nUnderground car park.\n"
        "2099-001: invented project.\n"        # not in the sources -> dropped
        "Some chatter without a number."
    )
    assert llm.format_project_answer(raw, PROJECTS) == (
        "- 2014-017 (2014, Marc Renard): timber arch footbridge.\n"
        "- 2016-023 (2016, Thomas Dubois): Underground car park."
    )


def test_project_answer_ignores_wrong_names_from_model():
    raw = "- 2014-017 (2019, Sophie Lambert): timber footbridge."
    assert llm.format_project_answer(raw, PROJECTS) == "- 2014-017 (2014, Marc Renard): timber footbridge."


def test_project_answer_nothing_usable():
    assert llm.format_project_answer("I think you should ask Marc.", PROJECTS) is None
