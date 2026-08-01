# Stock News Pipeline

A lightweight data pipeline that collects financial news and stock prices for a configurable set of tickers, 
deduplicates the results, and stores everything in a local SQLite database for later analysis and modeling.

News is sourced from the [Alpha Vantage `NEWS_SENTIMENT`](https://www.alphavantage.co/documentation/#news-sentiment) 
endpoint, which provides pre-computed per-article sentiment scores stored as a reference baseline.

---

## Features

- **News ingestion** - pulls the latest articles per ticker from Alpha Vantage, including headline, summary, source, URL, and reference sentiment.
- **Price ingestion** - fetches stock prices for the same tickers.
- **Deduplication** - stable article IDs derived from URLs prevent duplicate rows across runs.
- **SQLite storage** - everything persisted in a single portable `data/pipeline.db` file.
- **YAML configuration** - tickers, sources, and pipeline options in `config/config.yaml`.
- **`.env` secrets** - API keys stay out of the repo.
- **Rate-limit aware** - built-in pauses between requests to respect the Alpha Vantage free tier (5 req/min).

---

## Project Structure

```
stock-news-pipeline/
├── config/
│   └── config.yaml            # Tickers and pipeline settings
├── data/
│   └── pipeline.db            # SQLite database (generated)
├── scripts/
│   ├── init_db.py             # Creates the DB schema
│   └── run_pipeline.py        # Entry point - runs the full pipeline
├── src/
│   ├── db/
│   │   ├── connection.py      # DB connection + upsert helpers
│   │   └── schema.py          # Table definitions
│   ├── scraping/
│   │   ├── fetch_news.py      # Alpha Vantage news ingestion
│   │   └── fetch_prices.py    # Price ingestion
│   └── utils/
│       ├── config.py          # YAML config loader
│       └── dedupe.py          # Stable article ID hashing
├── .env                       # Secrets (not committed)
├── requirements.txt
└── README.md
```

---

## Getting Started

1. **Ensure prerequisites are installed:**
   - Python **3.12+**
   - `pip`
   - A free [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key)

2. **Clone the repository and enter the project directory.**

3. **Create and activate a virtual environment.**

4. **Install dependencies from `requirements.txt`.**

5. **Create a `.env` file in the project root** and add your Alpha Vantage API key as `ALPHA_VANTAGE_API_KEY`.

6. **Edit `config/config.yaml`** to set your tickers and pipeline options.

7. **Initialize the database** by running `scripts/init_db.py`.

8. **Run the pipeline** by running `scripts/run_pipeline.py`.

---

## How It Works

1. **Fetch** - `fetch_news.py` calls the Alpha Vantage `NEWS_SENTIMENT` endpoint for each configured ticker.
2. **Parse** - each raw article is normalized (ISO timestamps, extracted fields) into the shape expected by the `articles` table.
3. **Dedupe** - a stable `article_id` is computed from the article URL, so re-runs won't create duplicate rows.
4. **Upsert** - rows are written to SQLite via `upsert_articles()`; existing rows are left untouched.
5. **Throttle** - between tickers, the pipeline sleeps (default `12s`) to respect the free-tier rate limit.

---

## Data Model (high level)

| Table      | Purpose                                                                 |
|------------|-------------------------------------------------------------------------|
| `articles` | Deduplicated news: `article_id`, `ticker`, `source`, `published_at`, `headline`, `body`, `url` |
| `prices`   | Stock price rows per ticker and timestamp                               |

> Authoritative definitions live in `src/db/schema.py`.

---

## Tech Stack

- **Python 3.12**
- **requests** - HTTP client for the Alpha Vantage API
- **python-dotenv** - loads secrets from `.env`
- **PyYAML** - configuration
- **pandas** / **numpy** - data wrangling
- **SQLite** - storage

---

## Notes & Gotchas

- **Alpha Vantage free tier** is limited to **5 requests/minute** and **500 requests/day**. The pipeline pauses between tickers by default; adjust `pause_seconds` if needed.
- The API sometimes returns **HTTP 200 with a `Note` / `Information` message** when rate-limited. The pipeline detects this and raises a clear error rather than silently storing nothing.
- The sentiment score from Alpha Vantage is stored as a **reference baseline**; no derived labels are written to the `articles` table, keeping the pipeline horizon-agnostic.

---

## Roadmap

- [ ] Scheduled runs (cron / APScheduler)
- [ ] Custom sentiment model, compared against the Alpha Vantage baseline
- [ ] Export to Parquet / CSV
- [ ] Simple Flask dashboard
- [ ] Dockerfile


---

## License
Not yet licensed
```