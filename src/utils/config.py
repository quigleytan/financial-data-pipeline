"""
config.py

Loads config/config.yaml into a plain dict. Kept deliberately simple -
no schema validation library, no config classes - just enough structure
that fetch_prices.py and fetch_news.py can pull settings from one place
instead of hardcoding tickers/dates/limits.
"""

from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """
    Loads and returns the pipeline config as a dict.

    Raises:
        FileNotFoundError if config.yaml doesn't exist at the expected path.
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at {config_path}. "
            f"Did you create config/config.yaml?"
        )

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    config = load_config()
    print(config)