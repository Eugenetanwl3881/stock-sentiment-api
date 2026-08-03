"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config values, loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Scraper ─────────────────────────────────────────────────
    # Uses Reddit's public .json endpoints — no API key needed
    reddit_subreddit: str = "valueinvesting"
    reddit_post_limit: int = 100
    reddit_sort: str = "hot"  # hot, new, top, rising
    reddit_comment_limit: int = 5  # top-N comments to fetch per post (0 = skip)
    reddit_user_agent: str = "stock-sentiment-api/1.0"

    # ── Database ────────────────────────────────────────────────
    database_url: str = "sqlite:///./stock_sentiment.db"

    # ── Scheduler ───────────────────────────────────────────────
    schedule_scrape_hour: int = 8
    schedule_scrape_minute: int = 0

    # ── Server ──────────────────────────────────────────────────
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # ── LLM Ticker Extraction ─────────────────────
    # Set opencode_api_key in .env to enable LLM-based extraction
    opencode_api_key: str = ""
    opencode_model: str = "mimo-v2.5"  # cheapest ($0.14/M input), reasoning model
    opencode_base_url: str = "https://opencode.ai/zen/go/v1"


# Singleton — import this everywhere
settings = Settings()
