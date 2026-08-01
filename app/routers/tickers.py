"""GET /tickers/{ticker} — sentiment + fundamentals for one stock."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import StockMention, StockFundamentals, Post

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("/{ticker}")
def ticker_detail(ticker: str, db: Session = Depends(get_db)):
    """Return sentiment + fundamentals + recent posts for a ticker."""
    t = ticker.upper()

    mentions = (
        db.query(StockMention)
        .filter(StockMention.ticker == t, StockMention.sentiment_score != None)
        .all()
    )
    if not mentions:
        raise HTTPException(status_code=404, detail=f"No scored mentions found for {t}")

    avg_sentiment = round(
        float(sum(m.sentiment_score for m in mentions) / len(mentions)), 3
    )
    post_ids = [m.post_id for m in mentions]
    posts = (
        db.query(Post)
        .filter(Post.id.in_(post_ids))
        .order_by(Post.created_utc.desc())
        .limit(10)
        .all()
    )

    fundamentals = db.query(StockFundamentals).filter(
        StockFundamentals.ticker == t
    ).first()

    return {
        "ticker": t,
        "mention_count": len(mentions),
        "avg_sentiment": avg_sentiment,
        "fundamentals": {
            "score": fundamentals.fundamentals_score if fundamentals else None,
            "pe_ratio": fundamentals.pe_ratio if fundamentals else None,
            "forward_pe": fundamentals.forward_pe if fundamentals else None,
            "pb_ratio": fundamentals.pb_ratio if fundamentals else None,
            "debt_to_equity": fundamentals.debt_to_equity if fundamentals else None,
            "revenue_growth": fundamentals.revenue_growth if fundamentals else None,
            "profit_margins": fundamentals.profit_margins if fundamentals else None,
            "roe": fundamentals.roe if fundamentals else None,
            "market_cap": fundamentals.market_cap if fundamentals else None,
            "sector": fundamentals.sector if fundamentals else None,
        },
        "recent_posts": [
            {
                "title": p.title,
                "url": p.url,
                "score": p.score,
                "sentiment": next(
                    (m.sentiment_score for m in mentions if m.post_id == p.id), None
                ),
            }
            for p in posts
        ],
    }


@router.get("/{ticker}/fundamentals")
def ticker_fundamentals(ticker: str, db: Session = Depends(get_db)):
    """Return raw fundamentals data for a single ticker."""
    t = ticker.upper()
    row = db.query(StockFundamentals).filter(StockFundamentals.ticker == t).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"No fundamentals found for {t}")
    return {
        "ticker": row.ticker,
        "pe_ratio": row.pe_ratio,
        "forward_pe": row.forward_pe,
        "pb_ratio": row.pb_ratio,
        "debt_to_equity": row.debt_to_equity,
        "revenue_growth": row.revenue_growth,
        "profit_margins": row.profit_margins,
        "roe": row.roe,
        "market_cap": row.market_cap,
        "sector": row.sector,
        "fundamentals_score": row.fundamentals_score,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
