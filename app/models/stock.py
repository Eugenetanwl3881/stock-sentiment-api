"""SQLAlchemy ORM models for stock sentiment data."""
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reddit_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500))
    score: Mapped[int] = mapped_column(Integer, default=0)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    created_utc: Mapped[datetime] = mapped_column()
    scraped_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    # One post can mention many tickers
    mentions: Mapped[list["StockMention"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Post {self.reddit_id}: {self.title[:50]}>"


class StockMention(Base):
    __tablename__ = "stock_mentions"

    __table_args__ = (
        UniqueConstraint("post_id", "ticker", name="uq_post_ticker"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)

    post: Mapped["Post"] = relationship(back_populates="mentions")

    def __repr__(self) -> str:
        return f"<StockMention {self.ticker} in post {self.post_id}>"


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scraped_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    posts_found: Mapped[int] = mapped_column(Integer, default=0)
    new_posts_saved: Mapped[int] = mapped_column(Integer, default=0)
    tickers_found: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ScrapeLog {self.scraped_at}: {self.status}>"


class StockFundamentals(Base):
    """One row per distinct ticker. Refreshed periodically via aggregation step."""

    __tablename__ = "stock_fundamentals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    pe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    forward_pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pb_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    revenue_growth: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_margins: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fundamentals_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<StockFundamentals {self.ticker}: score={self.fundamentals_score}>"