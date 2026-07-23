"""
fetch_prices.py

Fetches daily OHLCV price data for a list of tickers using yfinance,
and caches it locally so we don't re-download on every run.
"""

import os
import pandas as pd
import yfinance as yf

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")


def fetch_price_history(ticker: str, start: str, end: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetch daily OHLCV data for a single ticker between start and end dates.

    Args:
        ticker: e.g. "AAPL"
        start: "YYYY-MM-DD"
        end: "YYYY-MM-DD"
        force_refresh: if True, re-download even if a cached file exists

    Returns:
        DataFrame indexed by date, columns: Open, High, Low, Close, Volume
    """
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    cache_path = os.path.join(RAW_DATA_DIR, f"{ticker}_prices.csv")

    if os.path.exists(cache_path) and not force_refresh:
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        # Only re-fetch if cache doesn't cover the requested range
        if df.index.min() <= pd.Timestamp(start) and df.index.max() >= pd.Timestamp(end):
            return df.loc[start:end]

    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No price data returned for {ticker} between {start} and {end}. "
                          f"Check the ticker symbol and date range.")

    # yfinance sometimes returns MultiIndex columns even for a single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.to_csv(cache_path)
    return df


def fetch_multiple(tickers: list, start: str, end: str, force_refresh: bool = False) -> dict:
    """
    Fetch price history for multiple tickers.

    Returns:
        dict of {ticker: DataFrame}
    """
    return {ticker: fetch_price_history(ticker, start, end, force_refresh) for ticker in tickers}


if __name__ == "__main__":
    # Quick manual test
    data = fetch_multiple(["AAPL", "MSFT"], start="2023-01-01", end="2024-01-01")
    for ticker, df in data.items():
        print(f"\n{ticker}: {len(df)} rows")
        print(df.head())