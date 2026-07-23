"""
schema.py

Defines the SQLite schema for the news/price pipeline and provides a
function to initialize the database (create tables if they don't exist).

Design notes:
- articles.article_id is a hash of the URL (see utils/dedupe.py) so that
  re-scraping the same article naturally upserts instead of duplicating.
- prices uses a composite primary key (ticker, date) since that's the
  natural unique identifier for a daily bar.
- No derived/labeled columns live here (no direction/magnitude/volatility) —
  those are horizon-dependent and belong to the downstream modeling project,
  not this pipeline. This DB is horizon-agnostic by design.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "pipeline.db"

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS articles (
        article_id      TEXT PRIMARY KEY,
        ticker          TEXT NOT NULL,
        source          TEXT,
        published_at    TIMESTAMP NOT NULL,
        headline        TEXT,
        body            TEXT,
        url             TEXT,
        scraped_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_articles_ticker_published
    ON articles (ticker, published_at);
    """,
    """
    CREATE TABLE IF NOT EXISTS prices (
        ticker  TEXT NOT NULL,
        date    DATE NOT NULL,
        open    REAL,
        high    REAL,
        low     REAL,
        close   REAL,
        volume  INTEGER,
        PRIMARY KEY (ticker, date)
    );
    """,
]


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """
    Creates the database file and all tables/indexes if they don't already
    exist. Safe to run multiple times (idempotent).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()


def list_tables(db_path: Path = DEFAULT_DB_PATH) -> list:
    """Returns the list of table names currently in the database — useful for tests/sanity checks."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DEFAULT_DB_PATH}")
    print(f"Tables: {list_tables()}")