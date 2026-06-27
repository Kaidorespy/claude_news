"""
Claude News Feed - LLM Rater
Uses Ollama to rate news items by interestingness and generate analysis.
"""

import requests
import json
import time
import os
from typing import Tuple
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class RaterConfig:
    model: str = os.getenv("OLLAMA_MODEL", "qwen3-coder:480b-cloud")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
    request_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    max_retries: int = 3
    retry_backoff: float = 2.0  # doubles each retry: 2s, 4s, 8s


class RaterError(Exception):
    """Rater couldn't get a usable response from the LLM."""


class NewsRater:
    """Rates news items using local LLM"""

    RATING_PROMPT = """You are rating news items about Anthropic/Claude for a personal news feed.

Rate this item from 1-5 stars based on how interesting/important it is:
- 1 star: Minor update, bug fix, routine maintenance
- 2 stars: Small feature, minor announcement
- 3 stars: Notable update, interesting discussion
- 4 stars: Significant news, important feature/change
- 5 stars: Major announcement, breaking news, critical update

{interests_block}ITEM:
Source: {source}
Title: {title}
Summary: {summary}
{body_block}URL: {url}

Respond in this exact JSON format:
{{
    "stars": <1-5>,
    "first_impressions": "<one sentence gut reaction>",
    "implications": "<what this means for users, 1-2 sentences>",
    "action_items": "<any actions to take, or 'None'>",
    "tldr": "<ultra-short summary, max 10 words>"
}}

JSON response:"""

    def __init__(self, config: RaterConfig = None):
        self.config = config or RaterConfig()

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API. Raises on failure."""
        url = f"{self.config.base_url}/api/generate"
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": 500
            }
        }
        response = requests.post(url, json=payload, timeout=self.config.request_timeout)
        response.raise_for_status()
        return response.json().get("response", "")

    def _parse_rating(self, response: str) -> Tuple[int, str]:
        """Parse LLM response. Raises RaterError if response isn't a real rating."""
        start = response.find('{')
        end = response.rfind('}') + 1
        if start < 0 or end <= start:
            raise RaterError("no JSON object in response")

        try:
            data = json.loads(response[start:end])
        except json.JSONDecodeError as e:
            raise RaterError(f"invalid JSON: {e}")

        # Reject error-payloads or junk that happen to be valid JSON
        if 'stars' not in data:
            raise RaterError(f"missing 'stars' field; got keys: {list(data.keys())[:5]}")

        try:
            stars = int(data['stars'])
        except (ValueError, TypeError):
            raise RaterError(f"bad stars value: {data.get('stars')!r}")

        if not 1 <= stars <= 5:
            raise RaterError(f"stars out of range: {stars}")

        # Require at least some analysis content — empty everything = garbage
        first = (data.get('first_impressions') or '').strip()
        tldr = (data.get('tldr') or '').strip()
        if not (first or tldr):
            raise RaterError("analysis fields empty")

        analysis = json.dumps({
            "first_impressions": first,
            "implications": (data.get('implications') or '').strip(),
            "action_items": (data.get('action_items') or 'None').strip(),
            "tldr": tldr,
        })
        return stars, analysis

    def rate_item(self, item: dict, interests: str = "") -> Tuple[int, str]:
        """
        Rate a news item, retrying on transient failures.

        interests: optional free-text from the user describing what they care
        about; nudges the rater without overriding the rubric.

        Returns:
            (stars, analysis_json) on success.
            (0, error_json) if all retries fail — item stays unrated so it
            gets picked up on the next refresh.
        """
        body = (item.get('body') or '').strip()
        body_block = f"Article body:\n{body[:2500]}\n\n" if body else ""

        interests = (interests or '').strip()
        interests_block = (
            f"USER INTERESTS (weight ratings toward these; do not override the rubric):\n{interests}\n\n"
            if interests else ""
        )

        prompt = self.RATING_PROMPT.format(
            source=item.get('source', 'UNK'),
            title=item.get('title', 'No title'),
            summary=(item.get('summary') or 'No summary')[:500],
            body_block=body_block,
            interests_block=interests_block,
            url=item.get('url', '')
        )

        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = self._call_ollama(prompt)
                return self._parse_rating(response)
            except (requests.exceptions.RequestException, RaterError) as e:
                last_error = f"{type(e).__name__}: {e}"
                if attempt < self.config.max_retries:
                    delay = self.config.retry_backoff * (2 ** (attempt - 1))
                    print(f"    attempt {attempt} failed ({last_error}); retrying in {delay:.0f}s")
                    time.sleep(delay)

        print(f"    all {self.config.max_retries} attempts failed: {last_error}")
        return 0, json.dumps({
            "error": last_error,
            "attempts": self.config.max_retries,
        })

    def rate_batch(self, items: list) -> list:
        """Rate multiple items, return list of (hash, stars, analysis)"""
        results = []
        for item in items:
            print(f"  Rating: {item.get('title', '')[:40]}...")
            stars, analysis = self.rate_item(item)
            results.append((item.get('content_hash'), stars, analysis))
        return results


# Quick test
if __name__ == "__main__":
    print("Rater Test")
    print("="*50)
    print("(Requires Ollama running)")
    print()

    rater = NewsRater()

    test_item = {
        'source': 'ANTH',
        'title': 'Claude 4.0 Released with Enhanced Reasoning',
        'summary': 'Anthropic announces Claude 4.0 with significantly improved reasoning capabilities and extended context window.',
        'url': 'https://anthropic.com/news/claude-4'
    }

    print(f"Testing with: {test_item['title']}")
    stars, analysis = rater.rate_item(test_item)
    print(f"Stars: {stars}")
    print(f"Analysis: {analysis}")
