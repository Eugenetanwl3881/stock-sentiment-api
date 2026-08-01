"""GET /recommendations — ranked stock picks."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.recommendation import generate_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
def list_recommendations(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return top-N stock recommendations ranked by composite score."""
    return generate_recommendations(db, limit=limit)
