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
from app.services.ticker_extractor_llm import extract_tickers_llm
from app.services.sentiment import analyze_sentiment

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


def _fetch_comments(session: requests.Session, post_id: str, limit: int) -> str:
    """Fetch top-N comments for a post. Returns concatenated comment bodies."""
    if limit <= 0:
        return ""
    try:
        url = f"{REDDIT_BASE}/comments/{post_id}.json?limit={limit}&depth=1&raw_json=1"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Reddit returns [post_data, comments_data]
        if len(data) < 2:
            return ""
        comments = data[1]["data"]["children"]
        bodies = []
        for child in comments:
            body = child["data"].get("body", "").strip()
            if body and body != "[deleted]" and body != "[removed]":
                bodies.append(body)
        return " ".join(bodies)
    except Exception:
        logger.debug("Failed to fetch comments for post %s", post_id)
        return ""


def _merge_mentions(regex_mentions: list, llm_tickers: list) -> list:
    """Merge regex and LLM ticker results, deduplicating by ticker."""
    seen = {m["ticker"] for m in regex_mentions}
    merged = list(regex_mentions)
    for t in llm_tickers:
        if t not in seen:
            seen.add(t)
            merged.append({"ticker": t, "count": 1})
    return merged


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
        comment_text = _fetch_comments(
            session, parsed["reddit_id"], settings.reddit_comment_limit
        )
        # slight delay between comment fetches to be polite
        time.sleep(0.5)

        post_text = " ".join(filter(None, [post.title, post.body, comment_text]))
        regex_mentions = extract_ticker_mentions(post_text)
        # LLM only when explicitly enabled in config
        llm_tickers = extract_tickers_llm(post_text) if settings.opencode_enabled else []
        mentions = _merge_mentions(regex_mentions, llm_tickers)
        sentiment_score = analyze_sentiment(post_text) if mentions else None
        if mentions:
            for mention in mentions:
                post.mentions.append(
                    StockMention(
                        ticker=mention["ticker"],
                        mention_count=mention["count"],
                        sentiment_score=sentiment_score,
                    )
                )

        db.add(post)
        saved_count += 1

    db.commit()
    logger.info("Saved %d new posts", saved_count)
    return saved_count