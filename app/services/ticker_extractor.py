"""Extract ticker-like mentions from text.

Design:
- Regex finds all 1-5 letter uppercase words.
- A stopword set filters obvious English words (avoids wasted lookups).
- Primary validation: a locally-cached set of S&P 500 tickers, downloaded fresh
  weekly from a maintained public dataset on GitHub.
- lru_cache ensures each symbol is checked at most once per process.
"""
import csv
import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Callable, FrozenSet, List, Optional

import requests

logger = logging.getLogger(__name__)

_TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z]{1,3})?)\b")

# Common English words that appear in all-caps in titles but are never stock tickers.
# This is a pre-filter optimisation — it avoids wasting lookups, not a validation.
_STOPWORDS: FrozenSet[str] = frozenset({
    "A", "AN", "AND", "ARE", "AS", "AT", "BE", "BUT", "BY", "CAN", "DO", "FOR",
    "FROM", "HAS", "HAD", "HE", "HER", "HIM", "HIS", "HOW", "IF", "IN", "IS",
    "IT", "ITS", "JUST", "LIKE", "ME", "MY", "NO", "NOT", "NOW", "OF", "ON",
    "OR", "OUR", "OUT", "OVER", "OWN", "PER", "SAYS", "SHE", "SO", "THE",
    "THEIR", "THEM", "THEN", "TO", "TOO", "UP", "US", "WAS", "WE", "WERE",
    "WHAT", "WHEN", "WHICH", "WHO", "WHY", "WILL", "WITH", "WOULD", "YET",
    "YOU", "YOUR",
    "ALL", "ANY", "ASK", "BEST", "BUY", "CALL", "CEO", "CFO", "DID", "DUE",
    "EDIT", "ELSE", "EPS", "ETF", "EVER", "FAR", "FEW", "FUND", "GAAP",
    "GET", "GOT", "HOLD", "HUGE", "IDK", "IMO", "IPO", "IRA", "JOB", "KEY",
    "LOT", "LOW", "MAY", "MUCH", "NEED", "NEW", "NEXT", "NONE", "NYSE",
    "ODD", "OFF", "OLD", "ONE", "ONLY", "OPTION", "PAST", "PAYS", "PUT",
    "Q1", "Q2", "Q3", "Q4", "REIT", "RIO", "RUN", "SAY", "SEE", "SOLD",
    "SOME", "STILL", "STOP", "SUCH", "TAKE", "TECH", "THAN", "THAT",
    "THIS", "TIPS", "TODAY", "TOP", "TWO", "USE", "USED", "USING", "VERY",
    "VIA", "WANT", "WAY", "WELL", "WENT", "YTD",
    "ALSO", "BACK", "BEEN", "CAME", "COST", "DOWN", "EACH", "EVEN", "FIND",
    "FIRST", "GIVE", "GOOD", "HERE", "HIGH", "INTO", "LAST", "LIFE", "LIKE",
    "LONG", "LOOK", "MADE", "MAKE", "MANY", "MORE", "MOST", "MUST", "NAME",
    "NEAR", "ONTO", "OPEN", "PART", "REAL", "RISK", "SAME", "SHOW", "SIDE",
    "SINCE", "SIZE", "SOON", "SURE", "THEN", "TURN", "VERY", "WAIT", "WEEK",
    "WORK", "YEAR", "ALPHA", "BETA", "CASH", "DEBT", "DEEP", "FOCUS", "HEDGE",
    "LARGE", "LEVERAGE", "MARGIN", "MONEY", "PRICE", "RATES", "RETURN",
    "SHARE", "SHORT", "SMALL", "STOCK", "STRONG", "VALUE", "WHILE", "WORTH",
})

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_CACHE_PATH = _CACHE_DIR / "tickers.json"
_CACHE_TTL = timedelta(days=30)
_SP500_URL = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/refs/heads/main/data/constituents.csv"
)


def _download_sp500_tickers() -> tuple[set[str], dict[str, str]]:
    """Download S&P 500 symbols and name→ticker map from the public CSV.

    Returns (tickers_set, name_to_ticker_dict).
    """
    tickers: set[str] = set()
    name_map: dict[str, str] = {}
    try:
        response = requests.get(_SP500_URL, timeout=30)
        response.raise_for_status()
        reader = csv.reader(io.StringIO(response.text))
        next(reader)  # skip header: Symbol, Security, GICS Sector, ...
        for row in reader:
            if not row:
                continue
            symbol = row[0].strip().upper()
            name = row[1].strip() if len(row) > 1 else ""
            if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z]{1,3})?", symbol) and name:
                tickers.add(symbol)
                # Normalize name: "Apple Inc." → "Apple"
                short = re.sub(r"\s+(Inc\.?|Corp\.?|Corporation|Company|Ltd\.?|PLC|AG|SA|& Co\.?)$", "", name, flags=re.IGNORECASE).strip()
                if short and short != symbol:
                    name_map[short.lower()] = symbol
                # Also add first word as alias (helps match "JPMorgan" → JPM)
                first_word = short.split()[0].lower() if short else ""
                if first_word and len(first_word) > 3 and first_word != short.lower():
                    name_map[first_word] = symbol
        logger.info("Downloaded %d S&P 500 tickers, %d name mappings", len(tickers), len(name_map))
    except Exception:
        logger.warning("Failed to download S&P 500 ticker list", exc_info=True)
    return tickers, name_map


def _load_cached_tickers() -> FrozenSet[str]:
    """Return cached ticker set, refreshing from S&P 500 CSV if needed."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if _CACHE_PATH.exists():
        try:
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            age = datetime.now(timezone.utc) - datetime.fromisoformat(data["updated"])
            if age < _CACHE_TTL:
                return frozenset(data["tickers"])
        except Exception:
            logger.warning("Corrupt ticker cache, re-downloading", exc_info=True)

    tickers, name_map = _download_sp500_tickers()
    if tickers:
        _CACHE_PATH.write_text(
            json.dumps({
                "updated": datetime.now(timezone.utc).isoformat(),
                "tickers": sorted(tickers),
                "name_map": name_map,
            }, indent=2),
            encoding="utf-8",
        )
    return frozenset(tickers) if tickers else frozenset()


_NAME_MAP_CACHE: Optional[dict[str, str]] = None


def get_name_map() -> dict[str, str]:
    """Return company-name → ticker mapping (e.g. 'apple' → 'AAPL'). Loaded from cache."""
    global _NAME_MAP_CACHE
    if _NAME_MAP_CACHE is not None:
        return _NAME_MAP_CACHE
    try:
        if _CACHE_PATH.exists():
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            _NAME_MAP_CACHE = data.get("name_map", {})
        else:
            _load_cached_tickers()  # triggers download
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            _NAME_MAP_CACHE = data.get("name_map", {})
    except Exception:
        _NAME_MAP_CACHE = {}
    return _NAME_MAP_CACHE


@lru_cache(maxsize=1)
def _get_ticker_set() -> FrozenSet[str]:
    """Singleton accessor for the cached ticker set."""
    return _load_cached_tickers()


@lru_cache(maxsize=2048)
def _is_known_ticker(symbol: str) -> bool:
    """Validate a candidate symbol against the cached S&P 500 ticker set."""
    normalized = symbol.strip().upper()
    if not normalized or len(normalized) > 5:
        return False
    if not re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z]{1,3})?", normalized):
        return False
    if normalized in _STOPWORDS:
        return False
    return normalized in _get_ticker_set()


def extract_ticker_mentions(
    text: str,
    validator: Optional[Callable[[str], bool]] = None,
) -> List[dict]:
    """Return ticker mentions in order of appearance.

    Each candidate is validated against a cached S&P 500 ticker set (refreshed
    weekly) — no hardcoded ticker whitelist.
    """
    if not text:
        return []

    check_symbol = validator or _is_known_ticker
    mentions: List[dict] = []
    seen: set[str] = set()

    for match in _TICKER_PATTERN.finditer(text.upper()):
        ticker = match.group(1).strip().upper()
        if ticker in seen:
            continue
        if not check_symbol(ticker):
            continue
        seen.add(ticker)
        mentions.append({"ticker": ticker, "count": 1})

    return mentions
