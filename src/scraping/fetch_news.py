"""
fetch_news.py

Fetches news articles (with sentiment scores) from Alpha Vantage's
NEWS_SENTIMENT endpoint and writes them into the pipeline's SQLite
database using upsert_articles() (see db/connection.py).

API docs: https://www.alphavantage.co/documentation/#news-sentiment

Supports optional time_from/time_to parameters (format: YYYYMMDDTHHMM) to
pull HISTORICAL news rather than only the most recent articles. This
matters for downstream modeling: news from "just now" has no known future
price outcome yet, so a modeling project needs news old enough that its
forward-looking labels can actually be computed. Without a date range,
this endpoint defaults to the latest news relative to today.
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


def fetch_news_raw(ticker: str, limit: int = 50, time_from: str = None, time_to: str = None) -> list:
    """
    Calls the Alpha Vantage NEWS_SENTIMENT endpoint for a single ticker
    and returns the raw list of article dicts from the API response.

    Args:
        ticker: e.g. "AAPL"
        limit: max articles to request (Alpha Vantage caps this at 1000,
               but the free tier's daily request limit is the real constraint)
        time_from: optional start of date range, format "YYYYMMDDTHHMM"
            (e.g. "20260601T0000"). Without this, Alpha Vantage returns
            only the most recent news relative to today.
        time_to: optional end of date range, same format as time_from.

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
    if time_from is not None:
        params["time_from"] = time_from
    if time_to is not None:
        params["time_to"] = time_to

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


def fetch_and_store_news(
    ticker: str, limit: int = 50, time_from: str = None, time_to: str = None, db_path=None
) -> int:
    """
    Fetches news for a single ticker and upserts it into the articles table.

    Args:
        ticker: e.g. "AAPL"
        limit: max articles to request
        time_from: optional "YYYYMMDDTHHMM" start of historical date range
        time_to: optional "YYYYMMDDTHHMM" end of historical date range
        db_path: optional override of the DB path -- mainly used by tests
                 to write into a throwaway DB instead of the real one.

    Returns:
        Number of new rows actually inserted (duplicates skipped).
    """
    raw_articles = fetch_news_raw(ticker, limit=limit, time_from=time_from, time_to=time_to)
    parsed = [_parse_article(raw, ticker) for raw in raw_articles]
    if db_path is not None:
        return upsert_articles(parsed, db_path=db_path)
    return upsert_articles(parsed)


def fetch_and_store_multiple(
    tickers: list, limit: int = 50, pause_seconds: float = 12.0, time_from: str = None, time_to: str = None
) -> dict:
    """
    Fetch and store news for multiple tickers, pausing between requests
    to respect Alpha Vantage's free-tier rate limit (5 requests/minute).

    Returns:
        dict of {ticker: rows_inserted}
    """
    results = {}
    for i, ticker in enumerate(tickers):
        results[ticker] = fetch_and_store_news(ticker, limit=limit, time_from=time_from, time_to=time_to)
        if i < len(tickers) - 1:
            time.sleep(pause_seconds)
    return results


def fetch_and_store_news_chunked(
    ticker: str,
    time_from: str,
    time_to: str,
    chunk_days: int = 14,
    limit_per_chunk: int = 50,
    pause_seconds: float = 12.0,
    db_path=None,
) -> int:
    """
    Fetches news across [time_from, time_to] by making several smaller
    requests over sub-windows, instead of one request over the whole range.

    Why this exists: Alpha Vantage's default sort is "latest first" WITHIN
    whatever date range you give it. A single request over a wide range
    still returns articles clustered near time_to (up to `limit` of them),
    not spread across the range -- so widening time_from alone doesn't
    give you date diversity, it just gives you the same near-time_to
    articles again (upsert then reports 0 new, since they're duplicates).

    Chunking into sub-windows forces each request to pull from a specific
    slice of the range, which is what actually produces articles spread
    across many distinct trading dates -- necessary for a training set
    where labels vary from row to row.

    Args:
        ticker: e.g. "AAPL"
        time_from, time_to: "YYYYMMDDTHHMM", the overall range to cover
        chunk_days: size of each sub-window in days
        limit_per_chunk: max articles requested per sub-window
        pause_seconds: pause between requests (rate limit)

    Returns:
        Total number of new rows inserted across all chunks.
    """
    from datetime import datetime, timedelta

    start = datetime.strptime(time_from, "%Y%m%dT%H%M")
    end = datetime.strptime(time_to, "%Y%m%dT%H%M")

    total_inserted = 0
    chunk_start = start
    first_chunk = True

    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end)

        if not first_chunk:
            time.sleep(pause_seconds)
        first_chunk = False

        inserted = fetch_and_store_news(
            ticker,
            limit=limit_per_chunk,
            time_from=chunk_start.strftime("%Y%m%dT%H%M"),
            time_to=chunk_end.strftime("%Y%m%dT%H%M"),
            db_path=db_path,
        )
        total_inserted += inserted
        print(f"  {ticker} chunk {chunk_start.date()} to {chunk_end.date()}: {inserted} new articles")

        chunk_start = chunk_end

    return total_inserted


if __name__ == "__main__":
    from src.utils.config import load_config

    config = load_config()
    tickers = config["tickers"]
    limit = config["news"]["limit_per_ticker"]
    pause_seconds = config["news"]["pause_seconds"]
    time_from = config["news"].get("time_from")
    time_to = config["news"].get("time_to")
    chunk_days = config["news"].get("chunk_days", 14)

    if time_from and time_to:
        # Historical range requested -> chunk it to get date-spread articles,
        # not just the latest ones within the range (see docstring on
        # fetch_and_store_news_chunked for why this matters).
        results = {}
        for i, ticker in enumerate(tickers):
            if i > 0:
                time.sleep(pause_seconds)
            print(f"Fetching {ticker} in {chunk_days}-day chunks from {time_from} to {time_to}...")
            results[ticker] = fetch_and_store_news_chunked(
                ticker, time_from=time_from, time_to=time_to,
                chunk_days=chunk_days, limit_per_chunk=limit, pause_seconds=pause_seconds,
            )
        print(f"\nNew articles inserted per ticker: {results}")
    else:
        results = fetch_and_store_multiple(tickers, limit=limit, pause_seconds=pause_seconds)
        print(f"New articles inserted per ticker: {results}")