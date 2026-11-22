"""Load the policy documents into the `chunks` table.

Each `## Heading` in a docs/*.md file becomes one chunk: {doc, section, text}.
"""
import sqlite3
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"


def parse_doc(path: Path) -> list[dict]:
    """Split one markdown file into chunks, one per '## ' section."""
    chunks = []
    section = None
    lines: list[str] = []

    def flush():
        if section and lines:
            # The files are hard-wrapped: join the lines into one paragraph.
            chunks.append({"doc": path.name, "section": section, "text": " ".join(lines)})

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            flush()
            section, lines = line[3:].strip(), []
        elif line and not line.startswith("# "):
            lines.append(line)
    flush()
    return chunks


def load_all_docs(docs_dir: Path = DOCS_DIR) -> list[dict]:
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(parse_doc(path))
    return chunks


def ingest_if_empty(conn: sqlite3.Connection, docs_dir: Path = DOCS_DIR) -> int:
    """Fill `chunks` from docs/ only if it is empty (safe to call on every start).

    Returns the number of chunks inserted (0 if already filled).
    """
    if conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] > 0:
        return 0
    chunks = load_all_docs(docs_dir)
    conn.executemany(
        "INSERT INTO chunks (doc, section, text) VALUES (:doc, :section, :text)", chunks
    )
    conn.commit()
    return len(chunks)


def get_chunks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT doc, section, text FROM chunks ORDER BY id").fetchall()
    return [dict(r) for r in rows]
