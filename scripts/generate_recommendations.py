"""Standalone script: generate and print stock recommendations."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.database import SessionLocal
from app.services.recommendation import generate_recommendations

if __name__ == "__main__":
    settings.debug = False
    import logging
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    db = SessionLocal()
    try:
        recs = generate_recommendations(db, limit=20)

        if not recs:
            print("No recommendations — need both sentiment and fundamentals data.")
        else:
            print(f"{'#':<3} {'Ticker':<6} {'Score':>6} {'Rating':<12} {'Ment':>4}  {'Disc%':>6}  Sector")
            print("-" * 70)
            for i, r in enumerate(recs, 1):
                disc = f"{r.get('discount_3m_pct', 0) or 0:+.1f}" if r.get('discount_3m_pct') is not None else "   N/A"
                print(
                    f"{i:<3} {r['ticker']:<6} {r['composite']:>6.1f} "
                    f"{r['rating']:<12} {r['mention_count']:>4}  {disc:>6}  {r['sector']}"
                )
    finally:
        db.close()
