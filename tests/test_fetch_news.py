"""
test_fetch_news.py

Tests for src/scraping/fetch_news.py. Focuses on the pure parsing logic
(_parse_article, _parse_av_timestamp) plus the rate-limit detection in
fetch_news_raw(), since those are the parts most likely to silently
break if Alpha Vantage ever changes its response shape.

Network calls are mocked throughout - these tests never hit the real
Alpha Vantage API.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.scraping.fetch_news import (
    _parse_article,
    _parse_av_timestamp,
    fetch_and_store_news,
    fetch_news_raw,
)


def test_parse_av_timestamp_converts_to_iso_format():
    assert _parse_av_timestamp("20240103T093000") == "2024-01-03T09:30:00"


def test_parse_article_extracts_expected_fields():
    raw = {
        "title": "Apple announces new product",
        "url": "https://example.com/apple-news-1",
        "time_published": "20240103T093000",
        "source": "Reuters",
        "summary": "Apple unveiled a new product today.",
    }

    parsed = _parse_article(raw, ticker="AAPL")

    assert parsed["ticker"] == "AAPL"
    assert parsed["source"] == "Reuters"
    assert parsed["headline"] == "Apple announces new product"
    assert parsed["body"] == "Apple unveiled a new product today."
    assert parsed["url"] == "https://example.com/apple-news-1"
    assert parsed["published_at"] == "2024-01-03T09:30:00"
    assert len(parsed["article_id"]) == 64  # sha256 hex digest


def test_parse_article_same_url_produces_same_article_id():
    """
    Two raw articles with the same URL (as would happen if the same
    story is tagged to multiple tickers) should collapse to the same
    article_id - this is what makes cross-ticker dedup work.
    """
    raw = {
        "title": "Market-wide story",
        "url": "https://example.com/shared-story",
        "time_published": "20240103T093000",
        "source": "Reuters",
        "summary": "Affects multiple companies.",
    }

    parsed_for_aapl = _parse_article(raw, ticker="AAPL")
    parsed_for_msft = _parse_article(raw, ticker="MSFT")

    assert parsed_for_aapl["article_id"] == parsed_for_msft["article_id"]


def test_fetch_news_raw_returns_feed_list(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "fake_key_for_testing")

    fake_response = MagicMock()
    fake_response.json.return_value = {"feed": [{"title": "Test article"}]}
    fake_response.raise_for_status.return_value = None

    with patch("src.scraping.fetch_news.requests.get", return_value=fake_response):
        articles = fetch_news_raw("AAPL")

    assert articles == [{"title": "Test article"}]


def test_fetch_news_raw_raises_on_rate_limit_message(monkeypatch):
    """
    Alpha Vantage returns HTTP 200 with a "Note" key instead of "feed"
    when you've hit the rate limit - this must raise clearly rather
    than silently returning an empty list (which would look like "no
    news today" instead of "we got throttled").
    """
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "fake_key_for_testing")

    fake_response = MagicMock()
    fake_response.json.return_value = {"Note": "Thank you for using Alpha Vantage! ..."}
    fake_response.raise_for_status.return_value = None

    with patch("src.scraping.fetch_news.requests.get", return_value=fake_response):
        with pytest.raises(RuntimeError, match="rate-limited"):
            fetch_news_raw("AAPL")


def test_fetch_and_store_news_dedupes_across_repeated_runs(temp_db_path, monkeypatch):
    """
    Integration-style test: same fake API response fetched twice should
    only insert once, exercising fetch_news_raw -> _parse_article ->
    upsert_articles end-to-end.
    """
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "fake_key_for_testing")

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "feed": [
            {
                "title": "Test article",
                "url": "https://example.com/test-article",
                "time_published": "20240103T093000",
                "source": "Reuters",
                "summary": "A test article.",
            }
        ]
    }
    fake_response.raise_for_status.return_value = None

    with patch("src.scraping.fetch_news.requests.get", return_value=fake_response):
        first_run = fetch_and_store_news("AAPL", db_path=temp_db_path)
        second_run = fetch_and_store_news("AAPL", db_path=temp_db_path)

    assert first_run == 1
    assert second_run == 0