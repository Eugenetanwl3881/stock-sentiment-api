"""VADER sentiment analysis for Reddit posts."""
import logging

from nltk.sentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()


def analyze_sentiment(text: str) -> float:
    """Return VADER compound score for text (-1 most negative, +1 most positive)."""
    if not text:
        return 0.0
    return float(_analyzer.polarity_scores(text)["compound"])
