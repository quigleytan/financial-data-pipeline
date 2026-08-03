"""
conftest.py

Shared pytest fixtures. The most important one is `temp_db_path`, which
gives every test its own throwaway SQLite file instead of writing into
the real data/pipeline.db - tests should never touch real pipeline data.
"""

import pytest

from src.db.schema import init_db


@pytest.fixture
def temp_db_path(tmp_path):
    """
    Returns a path to a fresh, initialized SQLite DB inside pytest's
    built-in tmp_path (auto-cleaned up after the test).
    """
    db_path = tmp_path / "test_pipeline.db"
    init_db(db_path)
    return db_path