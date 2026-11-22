"""Load the policy documents into the `chunks` table.

Each `## Heading` in a docs/*.md file becomes one chunk:
{doc, title, section, text}, where `title` is the file's `# Title`.
"""
import sqlite3
from pathlib import Path

from app import db

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"


def parse_doc(path: Path) -> list[dict]:
    """Split one markdown file into chunks, one per '## ' section."""
    chunks = []
    title = path.stem
    section = None
    lines: list[str] = []

    def flush():
        if section and lines:
            # The files are hard-wrapped: join the lines into one paragraph.
            chunks.append({"doc": path.name, "title": title, "section": section, "text": " ".join(lines)})

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            flush()
            section, lines = line[3:].strip(), []
        elif line.startswith("# "):
            title = line[2:].strip()  # e.g. "Expense policy"
        elif line:
            lines.append(line)
    flush()
    return chunks


def load_all_docs(docs_dir: Path = DOCS_DIR) -> list[dict]:
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(parse_doc(path))
    return chunks


def reload_docs(conn: sqlite3.Connection, docs_dir: Path = DOCS_DIR) -> int:
    """Replace the `chunks` table with the current content of docs/.

    Called on every start, so an edited policy is picked up after a restart.
    Chunks are only derived from the files, so nothing is lost; the questions
    and ratings live in another table and are kept.
    """
    chunks = load_all_docs(docs_dir)
    conn.execute("DROP TABLE IF EXISTS chunks")  # also upgrades older databases
    conn.executescript(db.SCHEMA)
    conn.executemany(
        "INSERT INTO chunks (doc, title, section, text) VALUES (:doc, :title, :section, :text)", chunks
    )
    conn.commit()
    return len(chunks)


def get_chunks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT doc, title, section, text FROM chunks ORDER BY id").fetchall()
    return [dict(r) for r in rows]
