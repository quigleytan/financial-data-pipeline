"""
test_schema.py

Tests for src/db/schema.py - table creation and idempotency.
"""

from src.db.schema import init_db, list_tables


def test_init_db_creates_expected_tables(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    tables = list_tables(db_path)
    assert "articles" in tables
    assert "prices" in tables


def test_init_db_is_idempotent(tmp_path):
    """
    Running init_db() twice against the same file shouldn't error or
    duplicate/reset anything - this matters because get_connection()
    calls init_db() on every single connection.
    """
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # should not raise

    tables = list_tables(db_path)
    assert tables.count("articles") == 1
    assert tables.count("prices") == 1