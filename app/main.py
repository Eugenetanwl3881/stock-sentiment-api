"""FastAPI application — stock sentiment + recommendations API."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base
from app.routers import recommendations, tickers, scrape
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on boot, clean up on shutdown."""
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield


app = FastAPI(
    title="Stock Sentiment API",
    description="Scrapes Reddit, extracts ticker mentions, scores sentiment + fundamentals, and returns ranked recommendations.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(recommendations.router)
app.include_router(tickers.router)
app.include_router(scrape.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "stock-sentiment-api"}
