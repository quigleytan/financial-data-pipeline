"""
schema.py

Defines the SQLite schema for the news/price pipeline and provides a
function to initialize the database.

Design notes:
- articles.article_id is a hash of the URL (see utils/dedupe.py) so that
  re-scraping the same article naturally upserts instead of duplicating.
- prices use a composite primary key (ticker, date) since that's the
  natural unique identifier for a daily bar.
- Purely raw data is stored in the DB, no transformations or calculations.
- Data is stored independent of data horizons (e.g., 1-day, 1-week, 1-month, etc.)
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
    """Returns the list of table names currently in the database"""
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