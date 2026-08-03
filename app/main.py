"""FastAPI application — stock sentiment + recommendations API."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base
from app.routers import recommendations, tickers, scrape, fundamentals
from app.scheduler import start_scheduler
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    Base.metadata.create_all(bind=engine)   # create tables if missing
    start_scheduler()                        # start background jobs
    yield  
    # ── SHUTDOWN ──


app = FastAPI(
    title="Stock Sentiment API",
    description="Scrapes Reddit, extracts ticker mentions, scores sentiment + fundamentals, and returns ranked recommendations.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(recommendations.router)
app.include_router(tickers.router)
app.include_router(scrape.router)
app.include_router(fundamentals.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "stock-sentiment-api", "version": settings.app_version}
