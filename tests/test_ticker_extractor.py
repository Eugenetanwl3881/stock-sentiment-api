import unittest

from app.services.ticker_extractor import extract_ticker_mentions


class TickerExtractorTests(unittest.TestCase):
    def test_extracts_real_ticker_mentions_without_hardcoded_whitelist(self):
        def fake_validator(symbol: str) -> bool:
            return symbol in {"AAPL", "TSLA", "NVDA", "AMD"}

        text = "I think AAPL and TSLA are strong, but not NVDA or AMD."
        mentions = extract_ticker_mentions(text, validator=fake_validator)

        self.assertEqual([item["ticker"] for item in mentions], ["AAPL", "TSLA", "NVDA", "AMD"])

    def test_ignores_common_false_positive_words(self):
        def fake_validator(symbol: str) -> bool:
            return symbol in {"AAPL", "TSLA"}

        text = "I like AAPL and TSLA, but I do not like the word BUY or USD."
        mentions = extract_ticker_mentions(text, validator=fake_validator)

        self.assertEqual([item["ticker"] for item in mentions], ["AAPL", "TSLA"])


if __name__ == "__main__":
    unittest.main()
