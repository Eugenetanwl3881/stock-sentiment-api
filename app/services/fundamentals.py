"""Fetch and score stock fundamentals via Yahoo Finance's API.

This runs as a separate aggregation step — not during scraping — because:
- Fundamentals don't change intraday; refreshing once per day is enough.
- Yahoo rate-limits; batching all tickers at once avoids 429s.
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.models.stock import StockMention, StockFundamentals

logger = logging.getLogger(__name__)

_STALENESS_THRESHOLD = timedelta(hours=12)
_FETCH_DELAY_SECONDS = 1.0  # polite pause between Yahoo API calls

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
})
_CRUMB: Optional[str] = None


def _get_crumb() -> str:
    """Get a fresh Yahoo crumb (cached per process)."""
    global _CRUMB
    if _CRUMB is not None:
        return _CRUMB

    # Visit Yahoo to get the A3 cookie
    _SESSION.get("https://fc.yahoo.com/", timeout=15)
    # Get crumb
    resp = _SESSION.get("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=15)
    resp.raise_for_status()
    _CRUMB = resp.text.strip()
    logger.debug("Got crumb: %s", _CRUMB[:8])
    return _CRUMB


def _fetch_metrics(ticker: str) -> Optional[dict]:
    """Pull key metrics directly from Yahoo Finance API. Returns None on failure."""
    for attempt in range(3):
        try:
            crumb = _get_crumb()
            url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
            params = {
                "modules": "summaryDetail,price,assetProfile,financialData,defaultKeyStatistics",
                "crumb": crumb,
            }
            resp = _SESSION.get(url, params=params, timeout=15)

            if resp.status_code == 429:
                wait = (attempt + 1) * 30
                logger.warning("Rate-limited, waiting %ds (attempt %d/3)", wait, attempt + 1)
                _CRUMB = None  # invalidate crumb
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            result = data.get("quoteSummary", {}).get("result")
            if not result:
                return None
            r = result[0]
            sd = r.get("summaryDetail") or {}
            ap = r.get("assetProfile") or {}
            fd = r.get("financialData") or {}
            dks = r.get("defaultKeyStatistics") or {}

            return {
                "ticker": ticker.upper(),
                "pe_ratio": _raw(sd, "trailingPE"),
                "forward_pe": _raw(sd, "forwardPE"),
                "pb_ratio": _raw(dks, "priceToBook"),
                "debt_to_equity": _raw(fd, "debtToEquity"),
                "revenue_growth": _raw(fd, "revenueGrowth"),
                "profit_margins": _raw(fd, "profitMargins"),
                "roe": _raw(fd, "returnOnEquity"),
                "market_cap": _raw(r.get("price") or {}, "marketCap"),
                "sector": ap.get("sector"),
            }
        except Exception as exc:
            msg = str(exc)
            if "429" in msg:
                wait = (attempt + 1) * 30
                logger.warning("Rate-limited for %s, waiting %ds (attempt %d/3)", ticker, wait, attempt + 1)
                _CRUMB = None
                time.sleep(wait)
            else:
                logger.debug("Fetch failed for %s: %s", ticker, exc)
                return None
    return None


def _raw(nested: dict, key: str) -> Optional[float]:
    """Extract raw numeric value from Yahoo's nested dict structure."""
    val = nested.get(key)
    if isinstance(val, dict):
        return val.get("raw")
    return val


def _score(metrics: dict) -> float:
    """Score fundamentals 0–100 with simple value-investing heuristics."""
    score = 50.0  # neutral baseline

    pe = metrics.get("pe_ratio")
    if pe is not None and 0 < pe < 25:
        score += 10

    rg = metrics.get("revenue_growth")
    if rg is not None and rg > 0.05:
        score += 15

    roe = metrics.get("roe")
    if roe is not None and roe > 0.10:
        score += 10

    de = metrics.get("debt_to_equity")
    if de is not None and de < 100:
        score += 10

    pm = metrics.get("profit_margins")
    if pm is not None and pm > 0.10:
        score += 10

    return min(score, 100.0)


def aggregate_fundamentals(db: Session) -> int:
    """Refresh fundamentals for all tickers mentioned in posts.

    Only fetches tickers whose data is stale (>12h old). Returns count of
    tickers updated.
    """
    cutoff = datetime.now(timezone.utc) - _STALENESS_THRESHOLD

    # Find all distinct tickers that need refreshing
    stale = (
        db.query(StockMention.ticker)
        .distinct()
        .outerjoin(
            StockFundamentals,
            StockMention.ticker == StockFundamentals.ticker,
        )
        .filter(
            (StockFundamentals.updated_at == None)
            | (StockFundamentals.updated_at < cutoff)
        )
        .all()
    )

    tickers = [row[0] for row in stale]
    total = len(tickers)
    logger.info("Found %d tickers needing fundamentals refresh", total)

    updated = 0
    skipped = 0
    for i, ticker in enumerate(tickers):
        # Progress every 5 tickers or on first/last
        if i == 0 or (i + 1) % 5 == 0 or i == total - 1:
            print(f"  [{i + 1}/{total}] {ticker} ...", flush=True)

        if i > 0:
            time.sleep(_FETCH_DELAY_SECONDS)

        metrics = _fetch_metrics(ticker)
        if metrics is None:
            skipped += 1
            continue

        fundamentals_score = _score(metrics)

        # Upsert: insert if new, update if exists
        existing = (
            db.query(StockFundamentals)
            .filter(StockFundamentals.ticker == ticker)
            .first()
        )
        if existing:
            for key, value in metrics.items():
                if key != "ticker":
                    setattr(existing, key, value)
            existing.fundamentals_score = fundamentals_score
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(
                StockFundamentals(
                    **metrics,
                    fundamentals_score=fundamentals_score,
                )
            )
        updated += 1

    db.commit()
    msg = f"Updated {updated} tickers ({skipped} skipped)"
    logger.info(msg)
    print(msg)
    return updated