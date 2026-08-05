"""LLM-based ticker extraction using OpenCode Go (or any OpenAI-compatible API).

This is an optional enhancement to the regex-based extractor. When an API key
is configured, the LLM can understand context like "Apple" → AAPL and avoid
false positives like "WANT" / "MET" / "T".
"""
import json
import logging
import time
from typing import List, Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)

_PROMPT = """Extract stock ticker symbols from this Reddit post. Return ONLY a JSON array of ticker strings.

Rules:
- Convert company names to tickers (e.g. "Apple" → AAPL, "Nvidia" → NVDA, "Google" → GOOGL, "Microsoft" → MSFT, "Berkshire Hathaway" → BRK.B, "JPMorgan" → JPM). Apply this for any company.
- Include tickers that appear directly in the text.
- Include tickers with $ prefix.
- Use context: if a short word is used as a stock ticker (e.g. "I bought T", "MET stock"), include it. If it's a common English word, skip it.
- Return empty array [] if no real stocks are mentioned.
- Be thorough — extract EVERY ticker or company name.

Text:
{text}

JSON:"""


def extract_tickers_llm(text: str) -> List[str]:
    """Use an LLM to extract ticker symbols from text. Returns list of tickers."""
    if not settings.opencode_api_key:
        return []

    if not settings.opencode_enabled:
        logger.debug("LLM disabled — set OPENCODE_ENABLED=true in .env")
        return []

    if not text or len(text) < 10:
        return []

    logger.info("LLM extraction starting for text (%d chars)...", len(text))

    try:
        start = time.monotonic()
        resp = requests.post(
            f"{settings.opencode_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.opencode_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.opencode_model,
                "messages": [
                    {"role": "user", "content": _PROMPT.format(text=text[:3000])}
                ],
                "max_tokens": 1000,
                "temperature": 0,
            },
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        message = payload["choices"][0]["message"]

        # Some models put output in content, others in reasoning/reasoning_content
        content = (
            message.get("content")
            or message.get("reasoning_content")
            or message.get("reasoning")
            or ""
        ).strip()

        # Parse the JSON array from the response
        if content.startswith("["):
            tickers = json.loads(content)
        else:
            # LLM might wrap it in ```json ... ```
            import re
            match = re.search(r"\[.*?\]", content, re.DOTALL)
            tickers = json.loads(match.group(0)) if match else []

        result = [t.upper().strip() for t in tickers if isinstance(t, str)]
        elapsed = time.monotonic() - start
        logger.info("LLM extracted %d tickers in %.1fs: %s", len(result), elapsed, result)
        return result

    except Exception:
        logger.warning("LLM extraction failed", exc_info=True)
        return []


# Quick self-test when run directly
if __name__ == "__main__":
    samples = [
        "I think Apple and Amazon are great buys right now.",
        "NVDA looks overvalued but MSFT and GOOGL are solid.",
        "Just bought more Berkshire Hathaway. Also like JPMorgan.",
        "The weather is nice today. Nothing about stocks here.",
    ]
    for s in samples:
        print(f"Text: {s}")
        print(f"  → {extract_tickers_llm(s)}")
        print()
