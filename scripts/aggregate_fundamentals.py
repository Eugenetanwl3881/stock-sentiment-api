"""Standalone script: refresh fundamentals for all tickers mentioned in DB."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.config import settings
from app.database import SessionLocal
from app.services.fundamentals import aggregate_fundamentals

if __name__ == "__main__":
    settings.debug = False

    db = SessionLocal()
    try:
        updated = aggregate_fundamentals(db)
        print(f"\nDone — {updated} tickers updated.")
    finally:
        db.close()
