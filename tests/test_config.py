"""
test_config.py

Tests for src/utils/config.py - the YAML config loader.
"""

import pytest

from src.utils.config import load_config


def test_load_config_returns_expected_keys(tmp_path):
    config_content = """
tickers:
  - AAPL
  - MSFT
prices:
  start_date: "2023-01-01"
  end_date: "2024-01-01"
news:
  limit_per_ticker: 50
  pause_seconds: 12.0
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)

    config = load_config(config_path)

    assert config["tickers"] == ["AAPL", "MSFT"]
    assert config["prices"]["start_date"] == "2023-01-01"
    assert config["news"]["limit_per_ticker"] == 50
    assert config["news"]["pause_seconds"] == 12.0


def test_load_config_missing_file_raises_clear_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.yaml"

    with pytest.raises(FileNotFoundError):
        load_config(missing_path)