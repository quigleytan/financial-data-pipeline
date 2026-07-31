"""
run_pipeline.py

Single entry point that runs the full pipeline: fetch prices, then fetch
news, both driven by config/config.yaml. This is what you'd point a cron
job (or just run manually) at, instead of calling fetch_prices.py and
fetch_news.py separately.

Usage:
    python -m scripts.run_pipeline
"""

from src.scraping.fetch_news import fetch_and_store_multiple as fetch_news_multiple
from src.scraping.fetch_prices import fetch_and_store_multiple as fetch_prices_multiple
from src.scraping.fetch_prices import get_existing_date_range
from src.utils.config import load_config


def run_pipeline() -> None:
    config = load_config()
    tickers = config["tickers"]

    print(f"Running pipeline for tickers: {tickers}")

    # --- Prices ---
    print("\n--- Fetching prices ---")
    start = config["prices"]["start_date"]
    end = config["prices"]["end_date"]

    try:
        price_results = fetch_prices_multiple(tickers, start=start, end=end)
        print(f"Rows affected per ticker: {price_results}")
        for ticker in tickers:
            print(f"{ticker}: stored range {get_existing_date_range(ticker)}")
    except Exception as e:
        # We don't want a price-fetch failure to prevent news from being
        # attempted - log it and move on rather than crashing the whole run.
        print(f"Price fetching failed: {e}")

    # --- News ---
    print("\n--- Fetching news ---")
    limit = config["news"]["limit_per_ticker"]
    pause_seconds = config["news"]["pause_seconds"]

    try:
        news_results = fetch_news_multiple(tickers, limit=limit, pause_seconds=pause_seconds)
        print(f"New articles inserted per ticker: {news_results}")
    except Exception as e:
        print(f"News fetching failed: {e}")

    print("\nPipeline run complete.")


if __name__ == "__main__":
    run_pipeline()