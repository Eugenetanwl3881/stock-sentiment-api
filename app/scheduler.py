"""APScheduler background jobs — auto-run scrape + fundamentals daily."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.services.scraper import scrape_subreddit
from app.services.fundamentals import aggregate_fundamentals

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _scrape_job():
    """Daily: scrape Reddit for new posts."""
    logger.info("Scheduled scrape starting...")
    db = SessionLocal()
    try:
        new = scrape_subreddit(db)
        logger.info("Scheduled scrape done — %d new posts", new)
    except Exception:
        logger.exception("Scheduled scrape failed")
    finally:
        db.close()


def _fundamentals_job():
    """Daily: refresh fundamentals for all mentioned tickers."""
    logger.info("Scheduled fundamentals aggregation starting...")
    db = SessionLocal()
    try:
        updated = aggregate_fundamentals(db)
        logger.info("Scheduled fundamentals done — %d tickers updated", updated)
    except Exception:
        logger.exception("Scheduled fundamentals failed")
    finally:
        db.close()


def start_scheduler():
    """Register jobs and start the background scheduler."""
    scheduler.add_job(
        _scrape_job,
        "cron",
        hour=8,
        minute=0,
        id="scrape_reddit",
        replace_existing=True,
    )
    scheduler.add_job(
        _fundamentals_job,
        "cron",
        hour=8,
        minute=15,
        id="aggregate_fundamentals",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — scrape at 08:00, fundamentals at 08:15 daily")
