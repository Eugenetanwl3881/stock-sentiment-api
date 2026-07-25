"""Recommendation engine: combines sentiment (40%) + fundamentals (60%).

Returns a ranked list of tickers with composite scores and ratings.
"""
import logging
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.stock import StockMention, StockFundamentals

logger = logging.getLogger(__name__)

_SENTIMENT_WEIGHT = 0.4
_FUNDAMENTALS_WEIGHT = 0.6


def _rating(composite: float) -> str:
    if composite >= 70:
        return "Strong Buy"
    if composite >= 55:
        return "Buy"
    if composite >= 40:
        return "Hold"
    return "Avoid"


def generate_recommendations(db: Session, limit: int = 20) -> List[dict]:
    """Return top-N tickers ranked by composite score (sentiment + fundamentals).

    Only includes tickers with both sentiment AND fundamentals data.
    Logs a warning for any ticker missing fundamentals so you can investigate.
    """
    # --- Warn about tickers with sentiment but no fundamentals ---
    missing = (
        db.query(StockMention.ticker)
        .distinct()
        .filter(StockMention.sentiment_score != None)
        .filter(
            ~StockMention.ticker.in_(
                db.query(StockFundamentals.ticker)
            )
        )
        .all()
    )
    if missing:
        ticker_list = sorted({row[0] for row in missing})
        logger.warning(
            "%d tickers have sentiment but no fundamentals: %s",
            len(ticker_list),
            ", ".join(ticker_list[:20]),
        )

    # --- Main query: only tickers with BOTH sentiment + fundamentals ---
    rows = (
        db.query(
            StockMention.ticker,
            func.count(StockMention.id).label("mention_count"),
            func.avg(StockMention.sentiment_score).label("avg_sentiment"),
            StockFundamentals.fundamentals_score,
            StockFundamentals.sector,
        )
        .join(  # INNER JOIN — only rows where fundamentals exist
            StockFundamentals,
            StockMention.ticker == StockFundamentals.ticker,
        )
        .filter(StockMention.sentiment_score != None)
        .group_by(StockMention.ticker)
        .order_by(
            (
                _SENTIMENT_WEIGHT * func.avg(StockMention.sentiment_score)
                + _FUNDAMENTALS_WEIGHT * StockFundamentals.fundamentals_score
            ).desc()
        )
        .limit(limit)
        .all()
    )

    results: List[dict] = []
    for row in rows:
        ticker, mention_count, avg_sentiment, fundamentals_score, sector = row
        composite = round(
            (float(avg_sentiment) * _SENTIMENT_WEIGHT)
            + (float(fundamentals_score) * _FUNDAMENTALS_WEIGHT),
            1,
        )
        results.append({
            "ticker": ticker,
            "mention_count": mention_count,
            "avg_sentiment": round(float(avg_sentiment), 3),
            "fundamentals_score": fundamentals_score,
            "composite": composite,
            "rating": _rating(composite),
            "sector": sector or "N/A",
        })

    logger.info("Generated %d recommendations", len(results))
    return results
