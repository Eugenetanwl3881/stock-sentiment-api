"""FastAPI application — stock sentiment + recommendations API."""
from fastapi import FastAPI

from app.database import engine, Base
from app.routers import recommendations, tickers, scrape

# Create tables on startup (safe to call multiple times)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Stock Sentiment API",
    description="Scrapes Reddit, extracts ticker mentions, scores sentiment + fundamentals, and returns ranked recommendations.",
    version="0.1.0",
)

app.include_router(recommendations.router)
app.include_router(tickers.router)
app.include_router(scrape.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "stock-sentiment-api"}
