"""SQLite storage: one file, three tables. Survives restarts."""
import os
import sqlite3
from pathlib import Path

# backend/corvalis.db by default; tests point this somewhere else.
DB_PATH = Path(os.getenv("CORVALIS_DB", Path(__file__).resolve().parent.parent / "corvalis.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id      INTEGER PRIMARY KEY,
    doc     TEXT NOT NULL,      -- e.g. 'leave.md'
    title   TEXT NOT NULL,      -- e.g. 'Leave and working time'
    section TEXT NOT NULL,      -- e.g. 'Annual leave'
    text    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY,
    number          TEXT NOT NULL UNIQUE,   -- e.g. '2019-042'
    title           TEXT NOT NULL,
    type            TEXT NOT NULL,
    discipline      TEXT NOT NULL,
    client          TEXT NOT NULL,
    city            TEXT NOT NULL,
    year            INTEGER NOT NULL,
    project_manager TEXT NOT NULL,
    materials       TEXT NOT NULL,
    budget_eur      INTEGER NOT NULL,
    summary         TEXT NOT NULL,
    folder_path     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id         INTEGER PRIMARY KEY,
    text       TEXT NOT NULL,
    scope      TEXT NOT NULL,       -- 'rules' or 'projects'
    answer     TEXT NOT NULL,
    found      INTEGER NOT NULL,    -- 1 if we had a matching source, else 0
    mode       TEXT NOT NULL,       -- 'ai' or 'search'
    rating     INTEGER NOT NULL DEFAULT 0,   -- -1, 0 or 1
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database (rows behave like dicts) and make sure tables exist."""
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
