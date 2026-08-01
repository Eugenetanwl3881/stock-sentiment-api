"""POST /scrape — manually trigger a Reddit scrape."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.scraper import scrape_subreddit

router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.post("")
def trigger_scrape(db: Session = Depends(get_db)):
    """Manually trigger a Reddit scrape. Returns count of new posts saved."""
    new = scrape_subreddit(db)
    return {"new_posts": new}
