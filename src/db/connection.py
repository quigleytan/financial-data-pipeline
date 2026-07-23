"""
connection.py

Wrapper around sqlite3 connections so the rest of the codebase doesn't
need to know the DB path or connection details directly. Also centralizes
common insert helpers used by both the news and price scrapers.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .schema import DEFAULT_DB_PATH, init_db


@contextmanager
def get_connection(db_path: Path = DEFAULT_DB_PATH):
    """
    Context manager that yields a sqlite3 connection, committing on success
    and rolling back on exception. Ensures the DB/tables exist first.

    Usage:
        with get_connection() as conn:
            conn.execute("SELECT * FROM articles")
    """
    init_db(db_path)  # no-op if already initialized, but guarantees tables exist
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_articles(articles: list, db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Insert articles, skipping any whose article_id already exists.

    Args:
        articles: list of dicts with keys matching the articles table columns
                  (article_id, ticker, source, published_at, headline, body, url)

    Returns:
        Number of rows actually inserted (duplicates are silently skipped).
    """
    if not articles:
        return 0

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        before = cursor.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

        cursor.executemany(
            """
            INSERT OR IGNORE INTO articles
                (article_id, ticker, source, published_at, headline, body, url)
            VALUES
                (:article_id, :ticker, :source, :published_at, :headline, :body, :url)
            """,
            articles,
        )

        after = cursor.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    return after - before


def upsert_prices(prices: list, db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Insert or replace daily price bars (ticker, date) is the natural key,
    so re-fetching the same-day overwrites values rather than duplicating.

    Args:
        prices: list of dicts with keys (ticker, date, open, high, low, close, volume)

    Returns:
        Number of rows affected.
    """
    if not prices:
        return 0

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO prices
                (ticker, date, open, high, low, close, volume)
            VALUES
                (:ticker, :date, :open, :high, :low, :close, :volume)
            """,
            prices,
        )
        affected = cursor.rowcount

    return affected