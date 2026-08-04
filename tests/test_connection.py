"""
test_connection.py

Tests for src/db/connection.py - upsert_articles() and upsert_prices().

These are the most important tests in the suite: they lock in the two
different upsert semantics the pipeline depends on (skip-duplicates for
articles, overwrite for prices) so a future refactor can't silently
change that behavior without a test failing.
"""

from src.db.connection import get_connection, upsert_articles, upsert_prices


def _make_article(article_id="a1", **overrides):
    article = {
        "article_id": article_id,
        "ticker": "AAPL",
        "source": "test-source",
        "published_at": "2024-01-02T09:00:00",
        "headline": "Test headline",
        "body": "Test body",
        "url": f"https://example.com/{article_id}",
    }
    article.update(overrides)
    return article


def test_upsert_articles_inserts_new_rows(temp_db_path):
    inserted = upsert_articles([_make_article("a1"), _make_article("a2")], db_path=temp_db_path)
    assert inserted == 2

    with get_connection(temp_db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert count == 2


def test_upsert_articles_skips_duplicate_ids(temp_db_path):
    """
    Re-inserting the same article_id (even with different content -
    simulating the source API returning a slightly-edited headline)
    should be skipped, not overwritten.
    """
    upsert_articles([_make_article("a1", headline="Original headline")], db_path=temp_db_path)
    inserted_second_time = upsert_articles(
        [_make_article("a1", headline="Edited headline")], db_path=temp_db_path
    )

    assert inserted_second_time == 0

    with get_connection(temp_db_path) as conn:
        row = conn.execute("SELECT headline FROM articles WHERE article_id = 'a1'").fetchone()
    assert row["headline"] == "Original headline"  # unchanged, not overwritten


def test_upsert_articles_empty_list_is_a_noop(temp_db_path):
    assert upsert_articles([], db_path=temp_db_path) == 0


def _make_price(ticker="AAPL", date="2024-01-02", close=100.0):
    return {
        "ticker": ticker,
        "date": date,
        "open": 99.0,
        "high": 101.0,
        "low": 98.0,
        "close": close,
        "volume": 1_000_000,
    }


def test_upsert_prices_inserts_new_rows(temp_db_path):
    affected = upsert_prices([_make_price(date="2024-01-02"), _make_price(date="2024-01-03")], db_path=temp_db_path)
    assert affected == 2


def test_upsert_prices_overwrites_same_ticker_and_date(temp_db_path):
    """
    Unlike articles, re-inserting the same (ticker, date) SHOULD overwrite
    - e.g. a corrected closing price for a day we already have.
    """
    upsert_prices([_make_price(date="2024-01-02", close=100.0)], db_path=temp_db_path)
    upsert_prices([_make_price(date="2024-01-02", close=105.0)], db_path=temp_db_path)

    with get_connection(temp_db_path) as conn:
        row = conn.execute(
            "SELECT close FROM prices WHERE ticker = 'AAPL' AND date = '2024-01-02'"
        ).fetchone()
    assert row["close"] == 105.0

    with get_connection(temp_db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    assert count == 1  # overwritten in place, not duplicated


def test_upsert_prices_empty_list_is_a_noop(temp_db_path):
    assert upsert_prices([], db_path=temp_db_path) == 0