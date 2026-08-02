"""POST /fundamentals/refresh — manually refresh fundamentals for all mentioned tickers."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.fundamentals import aggregate_fundamentals

router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])


@router.post("/refresh")
def refresh_fundamentals(db: Session = Depends(get_db)):
    """Manually trigger a fundamentals refresh. Returns count of tickers updated."""
    updated = aggregate_fundamentals(db)
    return {"tickers_updated": updated}
