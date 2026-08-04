"""
test_fetch_prices.py

Tests for src/scraping/fetch_prices.py. yfinance itself is mocked
throughout - these tests never hit the real network - so what's
actually being verified is the record-shaping and DB-writing logic
downstream of the yf.download() call.
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from src.db.connection import get_connection
from src.scraping.fetch_prices import fetch_and_store_prices, get_existing_date_range


def _fake_price_df(start="2024-01-02", n_days=5):
    dates = pd.bdate_range(start, periods=n_days)
    return pd.DataFrame(
        {
            "Open": np.linspace(100, 100 + n_days, n_days),
            "High": np.linspace(101, 101 + n_days, n_days),
            "Low": np.linspace(99, 99 + n_days, n_days),
            "Close": np.linspace(100.5, 100.5 + n_days, n_days),
            "Volume": np.full(n_days, 5_000_000),
        },
        index=dates,
    )


def test_fetch_and_store_prices_writes_expected_row_count(temp_db_path):
    fake_df = _fake_price_df(n_days=5)

    with patch("src.scraping.fetch_prices.yf.download", return_value=fake_df):
        affected = fetch_and_store_prices("AAPL", "2024-01-02", "2024-01-08", db_path=temp_db_path)

    assert affected == 5


def test_fetch_and_store_prices_raises_on_empty_response(temp_db_path):
    with patch("src.scraping.fetch_prices.yf.download", return_value=pd.DataFrame()):
        with pytest.raises(ValueError, match="No price data returned"):
            fetch_and_store_prices("BADTICKER", "2024-01-02", "2024-01-08", db_path=temp_db_path)


def test_get_existing_date_range_reflects_stored_data(temp_db_path):
    fake_df = _fake_price_df(start="2024-01-02", n_days=5)

    with patch("src.scraping.fetch_prices.yf.download", return_value=fake_df):
        fetch_and_store_prices("AAPL", "2024-01-02", "2024-01-08", db_path=temp_db_path)

    min_date, max_date = get_existing_date_range("AAPL", db_path=temp_db_path)
    assert min_date == "2024-01-02"
    assert max_date == "2024-01-08"


def test_get_existing_date_range_returns_none_for_unknown_ticker(temp_db_path):
    min_date, max_date = get_existing_date_range("NOPE", db_path=temp_db_path)
    assert min_date is None
    assert max_date is None


def test_rerunning_same_range_overwrites_not_duplicates(temp_db_path):
    """
    Re-fetching the same date range (e.g. running the pipeline twice in
    a day) should overwrite existing price rows, not create duplicates.
    """
    fake_df = _fake_price_df(start="2024-01-02", n_days=3)

    with patch("src.scraping.fetch_prices.yf.download", return_value=fake_df):
        fetch_and_store_prices("AAPL", "2024-01-02", "2024-01-05", db_path=temp_db_path)
        fetch_and_store_prices("AAPL", "2024-01-02", "2024-01-05", db_path=temp_db_path)

    with get_connection(temp_db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'").fetchone()[0]
    assert count == 3