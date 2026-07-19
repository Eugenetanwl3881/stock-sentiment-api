"""Scrapes posts from a subreddit using Reddit's public .json API."""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models.stock import Post, StockMention
from app.services.ticker_extractor import extract_ticker_mentions

logger = logging.getLogger(__name__)
REDDIT_BASE = "https://old.reddit.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def _build_url(sort: str, limit: int, after: Optional[str] = None) -> str:
    url = f"{REDDIT_BASE}/r/{settings.reddit_subreddit}/{sort}.json?limit={limit}&raw_json=1"
    if after:
        url += f"&after={after}"
    return url


def _parse_post(data: dict) -> dict:
    return {
        "reddit_id": data["id"],
        "title": data["title"],
        "body": data.get("selftext", "") or None,
        "author": data.get("author", "[deleted]"),
        "url": f"{REDDIT_BASE}{data['permalink']}",
        "score": data.get("score", 0),
        "num_comments": data.get("num_comments", 0),
        "created_utc": datetime.fromtimestamp(data["created_utc"], tz=timezone.utc),
    }


def scrape_subreddit(db: Session) -> int:
    """Fetch posts from r/valueinvesting, save new ones to DB. Returns count of new posts."""
    saved_count = 0

    session = requests.Session()
    session.headers.update(HEADERS)

    # First, visit the subreddit homepage to get cookies set
    session.get(f"{REDDIT_BASE}/r/{settings.reddit_subreddit}/", timeout=15)
    time.sleep(1)

    # Now fetch the JSON
    response = session.get(
        _build_url(settings.reddit_sort, settings.reddit_post_limit),
        timeout=30,
    )
    response.raise_for_status()
    posts = response.json()["data"]["children"]

    logger.info("Fetched %d posts from r/%s", len(posts), settings.reddit_subreddit)

    for child in posts:
        parsed = _parse_post(child["data"])

        existing = db.query(Post).filter(Post.reddit_id == parsed["reddit_id"]).first()
        if existing:
            continue

        post = Post(**parsed)
        post_text = " ".join(filter(None, [post.title, post.body]))
        mentions = extract_ticker_mentions(post_text)
        if mentions:
            for mention in mentions:
                post.mentions.append(
                    StockMention(
                        ticker=mention["ticker"],
                        mention_count=mention["count"],
                    )
                )

        db.add(post)
        saved_count += 1

    db.commit()
    logger.info("Saved %d new posts", saved_count)
    return saved_count