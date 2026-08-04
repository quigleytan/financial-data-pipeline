"""
fetch_prices.py

Fetches daily OHLCV price data via yfinance and writes it into the
pipeline's SQLite database using upsert_prices() (see db/connection.py).

Unlike the old CSV-based version, this module doesn't need its own caching
logic - the DB itself acts as the cache. We can always check what dates
we already have before deciding whether to hit the network again.
"""

import pandas as pd
import yfinance as yf

from src.db.connection import get_connection, upsert_prices


def get_existing_date_range(ticker: str, db_path=None) -> tuple:
    """
    Returns (min_date, max_date) already stored for this ticker, or
    (None, None) if we have nothing yet.
    """
    from src.db.schema import DEFAULT_DB_PATH
    path = db_path if db_path is not None else DEFAULT_DB_PATH
    with get_connection(path) as conn:
        row = conn.execute(
            "SELECT MIN(date), MAX(date) FROM prices WHERE ticker = ?",
            (ticker,),
        ).fetchone()
    return row[0], row[1]


def fetch_and_store_prices(ticker: str, start: str, end: str, db_path=None) -> int:
    """
    Downloads daily OHLCV data for a ticker between start and end dates
    and upserts it into the prices table.

    Args:
        ticker: e.g. "AAPL"
        start: "YYYY-MM-DD"
        end: "YYYY-MM-DD"
        db_path: optional override of the DB path - mainly used by tests
                 to write into a throwaway DB instead of the real one.

    Returns:
        Number of rows affected in the DB.
    """
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(
            f"No price data returned for {ticker} between {start} and {end}. "
            f"Check the ticker symbol and date range."
        )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    records = [
        {
            "ticker": ticker,
            "date": date.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        }
        for date, row in df.iterrows()
    ]

    if db_path is not None:
        return upsert_prices(records, db_path=db_path)
    return upsert_prices(records)


def fetch_and_store_multiple(tickers: list, start: str, end: str) -> dict:
    """
    Fetch and store price history for multiple tickers.

    Returns:
        dict of {ticker: rows_affected}
    """
    results = {}
    for ticker in tickers:
        results[ticker] = fetch_and_store_prices(ticker, start, end)
    return results


if __name__ == "__main__":
    from src.utils.config import load_config

    config = load_config()
    tickers = config["tickers"]
    start = config["prices"]["start_date"]
    end = config["prices"]["end_date"]

    results = fetch_and_store_multiple(tickers, start=start, end=end)
    print(f"Rows affected per ticker: {results}")

    for ticker in results:
        min_date, max_date = get_existing_date_range(ticker)
        print(f"{ticker}: stored range {min_date} to {max_date}")