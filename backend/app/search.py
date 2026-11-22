"""Keyword search with BM25 (no AI needed).

BM25 scores a document higher when it contains the query's words, especially
rare words, and does not over-reward long documents. Used for both policy
chunks (P1) and past projects (P9).
"""
import re
import unicodedata
from typing import Callable

from rank_bm25 import BM25Okapi

# A result counts as "found" only if BOTH are true:
#  - its BM25 score is at least MIN_SCORE, and
#  - it contains at least MIN_COVERAGE of the question's keywords (a keyword
#    also counts if one of its synonyms is there, see SYNONYMS).
# The second rule rejects e.g. "parental leave", which only matches the
# word "leave" in the sick-leave section. Tuned on tests/eval_questions.json,
# checked on the held-out tests/eval_holdout.json.
MIN_SCORE = 1.0
MIN_COVERAGE = 0.6           # company rules: be strict, never show an unrelated policy
MIN_COVERAGE_PROJECTS = 0.5  # past projects: a near match ("warehouse, but not in Antwerp") still helps

# Common words that carry no meaning for search.
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "at", "by", "with",
    "from", "is", "are", "be", "do", "does", "did", "i", "me", "my", "we", "our",
    "you", "your", "it", "its", "this", "that", "what", "which", "who", "how",
    "when", "where", "why", "can", "could", "should", "would", "will", "get", "have",
    "has", "need", "there", "any", "much", "many", "about", "if", "as", "so", "per",
    "before", "after", "up", "out", "not", "no", "am", "was", "were", "than",
    "take", "make", "want", "know", "tell", "please", "allowed", "may", "must",
    "long", "happen",  # as in "how long ...", "what happens ..."
    "use", "using", "just", "still", "anything", "something", "someone", "right",
    "since", "also", "only", "every", "all",
    "policy", "policies", "rule", "rules",  # "what's the policy on X": X is the keyword
    # Filler words in project questions ("have we designed a similar project before?")
    "design", "designed", "project", "projects", "similar", "like", "ever", "done",
    "past", "previous", "worked", "one", "some", "show", "find", "list", "corvalis",
}

# Everyday words -> the words the policies use. Only used on the question side
# (the documents are indexed as written). General office/HR vocabulary, not
# tied to particular test questions; see tests/eval_holdout.json for the check.
SYNONYMS = {
    # expenses
    "dinner": ["meal"], "food": ["meal"], "restaurant": ["meal"], "eat": ["meal"], "eating": ["meal"],
    "beer": ["alcohol"], "wine": ["alcohol"], "drink": ["alcohol"], "drinks": ["alcohol"],
    "cab": ["taxi"], "uber": ["taxi"],
    "train": ["public transport", "travel"], "bus": ["public transport"], "tram": ["public transport"],
    "metro": ["public transport"], "ticket": ["fare"], "tickets": ["fare"],
    "fuel": ["mileage", "kilometres"], "petrol": ["mileage"], "km": ["kilometres"],
    "driving": ["driven", "car"], "drive": ["driven", "car"], "commute": ["commuting"],
    "refund": ["reimbursed"], "refunded": ["reimbursed"], "repaid": ["reimbursed"], "costs": ["expense"],
    "boss": ["manager"], "sign": ["approval"], "deadline": ["submitted", "within"],
    "late": ["submitted", "within"],
    # IT
    "computer": ["laptop"], "pc": ["laptop"], "notebook": ["laptop"], "theft": ["stolen"],
    "took": ["stolen"], "missing": ["lost"],
    "wifi": ["public network"], "hotspot": ["public network"], "airport": ["public network"],
    "app": ["software"], "apps": ["software"], "program": ["software"], "programme": ["software"],
    "tool": ["software"], "download": ["install"],
    # leave
    "holiday": ["leave", "holiday"], "holidays": ["leave", "holiday"], "vacation": ["leave", "holiday"],
    "off": ["leave"], "weeks": ["days", "leave"], "pto": ["leave"],
    "ill": ["sick"], "illness": ["sick"], "flu": ["sick"],
    "doctor": ["medical certificate"], "doctors": ["medical certificate"], "note": ["certificate"],
    "telework": ["remote", "home"], "teleworking": ["remote", "home"], "remotely": ["remote"],
    "wfh": ["remote", "home"], "homeworking": ["remote", "home"],
    "christmas": ["public holiday"], "national": ["public"], "bank": ["public"],
    # onboarding
    "starter": ["newcomer", "first day"], "joiner": ["newcomer"], "hire": ["newcomer"],
    "hires": ["newcomer"], "join": ["newcomer", "first day"], "start": ["first day"],
    "mentor": ["buddy"], "trial": ["probation"], "evaluation": ["review"], "appraisal": ["review"],
    "email": ["mail"],
    # purchasing
    "buy": ["purchase"], "bought": ["purchase"], "order": ["ordered"], "monitor": ["screen"],
    "offer": ["quote"], "offers": ["quote"], "quotation": ["quote"], "quotations": ["quote"],
    "several": ["two"], "subscribe": ["subscription"], "licence": ["software", "subscription"],
    "license": ["software", "subscription"],
}

# Very small stemmer: cut one common ending so that word forms match,
# e.g. approves/approval/approved -> 'approv', install/installation -> 'install',
# applies/apply -> 'apply'.
SUFFIXES = ["ation", "ing", "ed", "es", "al", "s", "e"]


def stem(word: str) -> str:
    if word.endswith("ss"):  # 'class', 'business': leave alone
        return word
    if word.endswith(("ies", "ied")) and len(word) > 4:
        return word[:-3] + "y"  # applies/applied -> apply, policies -> policy
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def strip_accents(text: str) -> str:
    """'Liège' -> 'Liege', so people can type without accents."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def words_of(text: str) -> list[str]:
    """Lowercase words and numbers, without accents, HTML tags or stopwords."""
    text = re.sub(r"<[^>]*>", " ", text)  # pasted HTML: keep the text, not the tags
    words = re.findall(r"[^\W_]+", strip_accents(text.lower()).replace(",", ""))
    return [w for w in words if w not in STOPWORDS and len(w) >= 2]  # also drops the "m" of "I'm"


def tokenize(text: str) -> list[str]:
    """Searchable tokens of a document: words, stemmed."""
    return [stem(w) for w in words_of(text)]


def query_terms(question: str) -> list[set[str]]:
    """The question's keywords, each with its synonyms: [{'dinner', 'meal'}, ...]."""
    groups = []
    for w in words_of(question):
        group = {stem(w)}
        for synonym in SYNONYMS.get(w, []):
            group.update(tokenize(synonym))
        groups.append(group)
    return groups


class Index:
    """A BM25 index over a list of items (dicts).

    `text_of` says which text of an item is searchable.
    """

    def __init__(self, items: list[dict], text_of: Callable[[dict], str]):
        self.items = items
        self.tokens = [tokenize(text_of(item)) for item in items]
        self.bm25 = BM25Okapi(self.tokens)

    def search(self, query: str, k: int | None = 3) -> list[tuple[dict, float]]:
        """Top-k (item, score) pairs, best first (k=None: all items).
        Empty if the query has no keywords."""
        tokens = sorted({t for group in query_terms(query) for t in group})
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        order = sorted(range(len(self.items)), key=lambda i: scores[i], reverse=True)
        return [(self.items[i], float(scores[i])) for i in order[:k]]

    def is_relevant(
        self, query: str, results: list[tuple[dict, float]], min_coverage: float = MIN_COVERAGE
    ) -> bool:
        """Is the best result a real match? (see MIN_SCORE / MIN_COVERAGE above)"""
        groups = query_terms(query)
        if not results or not groups or results[0][1] < MIN_SCORE:
            return False
        # Numbers ("€3,000", "11pm") are the asker's own details, not
        # keywords of the documents, so they don't count against coverage.
        words = [g for g in groups if not any(ch.isdigit() for t in g for ch in t)]
        groups = words or groups
        best_tokens = set(self.tokens[self.items.index(results[0][0])])
        matched = sum(1 for g in groups if g & best_tokens)
        return matched / len(groups) >= min_coverage


def chunk_text(chunk: dict) -> str:
    """Policy chunks: the document title and the section title are searchable
    too. The section title counts double: it says what the section is about."""
    return f"{chunk.get('title', '')} {chunk['section']} {chunk['section']} {chunk['text']}"


def project_text(project: dict) -> str:
    """Past projects: what people search by, including who ran it and when.
    The type counts double, like a section title."""
    return " ".join([
        project["title"], project["type"], project["type"], project["materials"],
        project["city"], project["summary"], project["project_manager"],
        project["client"], str(project["year"]),
    ])
