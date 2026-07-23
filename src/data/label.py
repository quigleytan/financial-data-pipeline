"""
label.py

Given daily OHLCV price data, computes forward-looking labels for a
prediction horizon:
    - direction: sign of the forward return (1, -1, or 0)
    - magnitude: the forward % return
    - volatility: realized volatility (std of daily returns) over the
      forward window

"Forward-looking" means: for a given date, we look ahead N trading days
and compute what actually happened. These become the training labels
for whatever news was published on/before that date.
"""

import numpy as np
import pandas as pd

HORIZON_TRADING_DAYS = {
    "3day": 3,
    "weekly": 5,   # 5 trading days ≈ 1 calendar week
}


def compute_labels(df: pd.DataFrame, horizon: str = "weekly", flat_threshold: float = 0.0) -> pd.DataFrame:
    """
    Compute forward direction, magnitude, and volatility labels for each date.

    Args:
        df: DataFrame with a 'Close' column, indexed by trading date (ascending).
        horizon: one of "3day" or "weekly" (see HORIZON_TRADING_DAYS).
        flat_threshold: if abs(return) is below this, direction is labeled 0 (flat)
            instead of +1/-1. Default 0.0 means no flat category (pure sign).

    Returns:
        A new DataFrame with columns: direction, magnitude, volatility.
        The last `n_days` rows will have NaN labels since we don't yet know
        the future — these rows must be dropped before training.
    """
    if horizon not in HORIZON_TRADING_DAYS:
        raise ValueError(f"horizon must be one of {list(HORIZON_TRADING_DAYS.keys())}, got '{horizon}'")

    n_days = HORIZON_TRADING_DAYS[horizon]

    close = df["Close"]

    # Forward return: (price N days ahead / price today) - 1
    forward_price = close.shift(-n_days)
    magnitude = (forward_price / close) - 1

    # Direction from magnitude, with an optional "flat" dead zone
    direction = np.where(
        magnitude.abs() < flat_threshold, 0,
        np.where(magnitude > 0, 1, -1)
    )
    direction = pd.Series(direction, index=df.index).astype(float)
    direction[magnitude.isna()] = np.nan  # preserve NaNs where we don't have future data

    # Realized volatility over the forward window: std of daily log returns
    daily_log_returns = np.log(close / close.shift(1))
    volatility = daily_log_returns.rolling(window=n_days).std().shift(-n_days)

    labels = pd.DataFrame({
        "direction": direction,
        "magnitude": magnitude,
        "volatility": volatility,
    }, index=df.index)

    return labels


def sanity_check(df: pd.DataFrame, labels: pd.DataFrame, sample_size: int = 10, seed: int = 0) -> pd.DataFrame:
    """
    Pulls a random sample of dates with their price context and computed
    labels side by side, for manual eyeballing. This is the "print 10
    random weeks and check by hand" step.
    """
    valid_idx = labels.dropna().index
    rng = np.random.default_rng(seed)
    sample_dates = rng.choice(valid_idx, size=min(sample_size, len(valid_idx)), replace=False)
    sample_dates = sorted(sample_dates)

    rows = []
    for date in sample_dates:
        close_today = df.loc[date, "Close"]
        row = {
            "date": date,
            "close_today": round(close_today, 2),
            "direction": labels.loc[date, "direction"],
            "magnitude_pct": round(labels.loc[date, "magnitude"] * 100, 2),
            "volatility": round(labels.loc[date, "volatility"], 4),
        }
        rows.append(row)

    return pd.DataFrame(rows).set_index("date")


if __name__ == "__main__":
    from _synthetic_test_data import generate_fake_price_data

    df = generate_fake_price_data()
    labels = compute_labels(df, horizon="weekly")

    print("Label distribution (dropping NaN rows for the last horizon days):")
    print(labels.dropna()["direction"].value_counts())

    print("\nSanity check sample (verify magnitude sign matches direction, and eyeball against real chart logic):")
    print(sanity_check(df, labels))