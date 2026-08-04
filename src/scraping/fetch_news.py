"""
fetch_news.py

Fetches news articles (with sentiment scores) from Alpha Vantage's
NEWS_SENTIMENT endpoint and writes them into the pipeline's SQLite
database using upsert_articles() (see db/connection.py).

API docs: https://www.alphavantage.co/documentation/#news-sentiment

Note: Alpha Vantage's free tier includes a pre-computed sentiment score
per article. We store it for now as a reference/baseline (useful later
to compare against our own model), but the pipeline itself stays
horizon-agnostic - no derived labels live in this table.
"""

import os
import time

import requests
from dotenv import load_dotenv

from src.db.connection import upsert_articles
from src.utils.dedupe import make_article_id

load_dotenv()

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"


def _get_api_key() -> str:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ALPHA_VANTAGE_API_KEY not set. Add it to a .env file in the "
            "project root (see .env.example)."
        )
    return api_key


def fetch_news_raw(ticker: str, limit: int = 50) -> list:
    """
    Calls the Alpha Vantage NEWS_SENTIMENT endpoint for a single ticker
    and returns the raw list of article dicts from the API response.

    Args:
        ticker: e.g. "AAPL"
        limit: max articles to request (Alpha Vantage caps this at 1000,
               but the free tier's daily request limit is the real constraint)

    Returns:
        List of raw article dicts, as returned by the API under the
        "feed" key. Empty list if none found.
    """
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "limit": limit,
        "apikey": _get_api_key(),
    }

    response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "Note" in data or "Information" in data:
        # Alpha Vantage returns HTTP 200 even when you've hit a rate limit,
        # with an explanatory message instead of a "feed" key.
        raise RuntimeError(f"Alpha Vantage API message (likely rate-limited): {data}")

    return data.get("feed", [])


def _parse_article(raw: dict, ticker: str) -> dict:
    """
    Converts a single raw Alpha Vantage article dict into the shape our
    articles table expects.
    """
    url = raw["url"]
    return {
        "article_id": make_article_id(url),
        "ticker": ticker,
        "source": raw.get("source"),
        "published_at": _parse_av_timestamp(raw["time_published"]),
        "headline": raw.get("title"),
        "body": raw.get("summary"),
        "url": url,
    }


def _parse_av_timestamp(raw_ts: str) -> str:
    """
    Alpha Vantage timestamps look like '20240103T093000'. Convert to
    ISO format ('2024-01-03T09:30:00') for consistent storage.
    """
    return f"{raw_ts[0:4]}-{raw_ts[4:6]}-{raw_ts[6:8]}T{raw_ts[9:11]}:{raw_ts[11:13]}:{raw_ts[13:15]}"


def fetch_and_store_news(ticker: str, limit: int = 50, db_path=None) -> int:
    """
    Fetches news for a single ticker and upserts it into the articles table.

    Args:
        ticker: e.g. "AAPL"
        limit: max articles to request
        db_path: optional override of the DB path (defaults to DEFAULT_DB_PATH
                 via upsert_articles if not provided) - mainly used by tests
                 to write into a throwaway DB instead of the real one.

    Returns:
        Number of new rows actually inserted (duplicates skipped).
    """
    raw_articles = fetch_news_raw(ticker, limit=limit)
    parsed = [_parse_article(raw, ticker) for raw in raw_articles]
    if db_path is not None:
        return upsert_articles(parsed, db_path=db_path)
    return upsert_articles(parsed)


def fetch_and_store_multiple(tickers: list, limit: int = 50, pause_seconds: float = 12.0) -> dict:
    """
    Fetch and store news for multiple tickers, pausing between requests
    to respect Alpha Vantage's free-tier rate limit (5 requests/minute).

    Returns:
        dict of {ticker: rows_inserted}
    """
    results = {}
    for i, ticker in enumerate(tickers):
        results[ticker] = fetch_and_store_news(ticker, limit=limit)
        if i < len(tickers) - 1:
            time.sleep(pause_seconds)
    return results


if __name__ == "__main__":
    from src.utils.config import load_config

    config = load_config()
    tickers = config["tickers"]
    limit = config["news"]["limit_per_ticker"]
    pause_seconds = config["news"]["pause_seconds"]

    results = fetch_and_store_multiple(tickers, limit=limit, pause_seconds=pause_seconds)
    print(f"New articles inserted per ticker: {results}")