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
#  - it contains at least MIN_COVERAGE of the question's keywords.
# The second rule rejects e.g. "parental leave", which only matches the
# word "leave" in the sick-leave section. Tuned on tests/test_search.py.
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
    # Filler words in project questions ("have we designed a similar project before?")
    "design", "designed", "project", "projects", "similar", "like", "ever", "done",
    "past", "previous", "worked", "one", "some", "show", "find", "list", "corvalis",
}

# Very small stemmer: cut one common ending so that word forms match,
# e.g. approves/approval/approved -> 'approv', install/installation -> 'install'.
SUFFIXES = ["ation", "ing", "ed", "es", "al", "s", "e"]


def stem(word: str) -> str:
    if word.endswith("ss"):  # 'class', 'business': leave alone
        return word
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def strip_accents(text: str) -> str:
    """'Liège' -> 'Liege', so people can type without accents."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """Lowercase, remove accents, keep words/numbers, drop stopwords, stem."""
    words = re.findall(r"[^\W_]+", strip_accents(text.lower()).replace(",", ""))
    tokens = []
    for w in words:
        if w in STOPWORDS or len(w) < 2:  # also drops the "m" of "I'm"
            continue
        tokens.append(stem(w))
    return tokens


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
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        order = sorted(range(len(self.items)), key=lambda i: scores[i], reverse=True)
        return [(self.items[i], float(scores[i])) for i in order[:k]]

    def is_relevant(
        self, query: str, results: list[tuple[dict, float]], min_coverage: float = MIN_COVERAGE
    ) -> bool:
        """Is the best result a real match? (see MIN_SCORE / MIN_COVERAGE above)"""
        query_tokens = set(tokenize(query))
        if not results or not query_tokens or results[0][1] < MIN_SCORE:
            return False
        # Numbers ("€3,000", "11pm") are the asker's own details, not
        # keywords of the documents, so they don't count against coverage.
        words = {t for t in query_tokens if not any(ch.isdigit() for ch in t)}
        query_tokens = words or query_tokens
        best_tokens = set(self.tokens[self.items.index(results[0][0])])
        coverage = len(query_tokens & best_tokens) / len(query_tokens)
        return coverage >= min_coverage


def chunk_text(chunk: dict) -> str:
    """Policy chunks: the section title is searchable too, and counts double
    because it says what the whole section is about."""
    return f"{chunk['section']} {chunk['section']} {chunk['text']}"


def project_text(project: dict) -> str:
    """Past projects: what people search by. The type counts double, like a section title."""
    return " ".join([
        project["title"], project["type"], project["type"], project["materials"],
        project["city"], project["summary"],
    ])
