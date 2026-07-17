# Stock Sentiment API 🚧

Scrapes Reddit's r/valueinvesting, extracts stock tickers, analyzes sentiment, pulls Yahoo Finance fundamentals, and generates Buy/Hold/Sell recommendations.

## Tech Stack

| Layer        | Technology                        |
| ------------ | --------------------------------- |
| Framework    | FastAPI                           |
| Database     | SQLite + SQLAlchemy               |
| Scraping     | httpx (Reddit public `.json` API) |
| Sentiment    | NLTK VADER                        |
| Fundamentals | yfinance                          |
| Scheduling   | APScheduler                       |
| Config       | pydantic-settings                 |

## Getting Started

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/stock-sentiment-api.git
cd stock-sentiment-api

# Virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate       # macOS / Linux

# Install
pip install -r requirements.txt
python -c "import nltk; nltk.download('vader_lexicon')"

# Configure
cp .env.example .env

# Run (once built)
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```
