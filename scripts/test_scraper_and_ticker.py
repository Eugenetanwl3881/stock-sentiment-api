import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.stock import Post
from app.services.scraper import scrape_subreddit
from app.services.ticker_extractor import extract_ticker_mentions


if __name__ == "__main__":
    print("Testing ticker extractor...")
    sample_text = "AAPL and TSLA look strong, while NVDA is also in focus."
    print(extract_ticker_mentions(sample_text))

    print("\nTesting scraper...")
    db = SessionLocal()
    try:
        count = scrape_subreddit(db)
        print(f"Scraper saved {count} new posts")
        print("Recent posts in DB:")
        recent_posts = db.query(Post).order_by(Post.created_utc.desc()).limit(5).all()
        for post in recent_posts:
            print(f"- {post.reddit_id}: {post.title[:80]}")
    finally:
        db.close()
