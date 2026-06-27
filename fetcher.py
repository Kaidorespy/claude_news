"""
Claude News Feed - Source Fetcher
Scrapes and aggregates news about Anthropic/Claude from multiple sources.
"""

import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional
import hashlib
import json
import re

@dataclass
class NewsItem:
    """A single news item"""
    source: str          # "ANTH", "REUT", "BLOG", etc.
    title: str
    url: str
    summary: str
    published: datetime
    content_hash: str    # for deduplication
    stars: int = 0       # 1-5, set by LLM
    analysis: str = ""   # LLM's take

    def to_dict(self):
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "published": self.published.isoformat(),
            "content_hash": self.content_hash,
            "stars": self.stars,
            "analysis": self.analysis
        }


class SourceFetcher:
    """Base class for fetching from a source"""

    SOURCE_CODE = "UNK"

    def fetch(self) -> List[NewsItem]:
        raise NotImplementedError

    def _hash_content(self, title: str, url: str) -> str:
        """Create hash for deduplication"""
        content = f"{title.lower().strip()}{url.lower().strip()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class AnthropicBlogFetcher(SourceFetcher):
    """Fetch from Anthropic's official blog/news"""

    SOURCE_CODE = "ANTH"
    BLOG_URL = "https://www.anthropic.com/news"

    def fetch(self) -> List[NewsItem]:
        items = []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.BLOG_URL, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find article links - this selector may need adjustment
            articles = soup.find_all('a', href=re.compile(r'/news/'))

            seen_urls = set()
            for article in articles[:20]:  # limit to recent
                href = article.get('href', '')
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                url = f"https://www.anthropic.com{href}" if href.startswith('/') else href
                title = article.get_text(strip=True)[:100]

                if title and len(title) > 5:
                    items.append(NewsItem(
                        source=self.SOURCE_CODE,
                        title=title,
                        url=url,
                        summary="",
                        published=datetime.now(),  # would need to parse actual date
                        content_hash=self._hash_content(title, url)
                    ))
        except Exception as e:
            print(f"[{self.SOURCE_CODE}] Error: {e}")

        return items


class RSSFetcher(SourceFetcher):
    """Generic RSS feed fetcher"""

    def __init__(self, feed_url: str, source_code: str):
        self.feed_url = feed_url
        self.SOURCE_CODE = source_code

    def fetch(self) -> List[NewsItem]:
        items = []
        try:
            feed = feedparser.parse(self.feed_url)

            for entry in feed.entries[:20]:
                published = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                items.append(NewsItem(
                    source=self.SOURCE_CODE,
                    title=entry.get('title', 'No title')[:100],
                    url=entry.get('link', ''),
                    summary=entry.get('summary', '')[:300],
                    published=published,
                    content_hash=self._hash_content(entry.get('title', ''), entry.get('link', ''))
                ))
        except Exception as e:
            print(f"[{self.SOURCE_CODE}] RSS Error: {e}")

        return items


class NewsAPIFetcher(SourceFetcher):
    """
    Fetch from NewsAPI.org (free tier: 100 requests/day)
    Searches for 'anthropic' OR 'claude ai'
    """

    SOURCE_CODE = "NEWS"

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def fetch(self) -> List[NewsItem]:
        if not self.api_key:
            print("[NEWS] No API key configured - skipping")
            return []

        items = []
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": "anthropic OR \"claude ai\"",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": self.api_key
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for article in data.get("articles", []):
                published = datetime.now()
                if article.get("publishedAt"):
                    try:
                        published = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
                    except:
                        pass

                items.append(NewsItem(
                    source=self.SOURCE_CODE,
                    title=article.get("title", "")[:100],
                    url=article.get("url", ""),
                    summary=article.get("description", "")[:300],
                    published=published,
                    content_hash=self._hash_content(article.get("title", ""), article.get("url", ""))
                ))
        except Exception as e:
            print(f"[NEWS] API Error: {e}")

        return items


class RedditFetcher(SourceFetcher):
    """Fetch from Reddit using RSS (more reliable than JSON API)"""

    SOURCE_CODE = "RDIT"

    def __init__(self, subreddits: List[str] = None):
        self.subreddits = subreddits or ["anthropic", "ClaudeAI", "LocalLLaMA"]

    def fetch(self) -> List[NewsItem]:
        items = []

        for sub in self.subreddits:
            try:
                # Use RSS feed instead of JSON - less likely to be blocked
                url = f"https://www.reddit.com/r/{sub}/new.rss"
                feed = feedparser.parse(url)

                for entry in feed.entries[:10]:
                    published = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])

                    items.append(NewsItem(
                        source=self.SOURCE_CODE,
                        title=entry.get('title', '')[:100],
                        url=entry.get('link', ''),
                        summary=entry.get('summary', '')[:300],
                        published=published,
                        content_hash=self._hash_content(entry.get('title', ''), entry.get('link', ''))
                    ))
            except Exception as e:
                print(f"[RDIT] r/{sub} RSS Error: {e}")

        return items


class HackerNewsFetcher(SourceFetcher):
    """Fetch from Hacker News - search for anthropic/claude mentions"""

    SOURCE_CODE = "HN"

    def fetch(self) -> List[NewsItem]:
        items = []

        try:
            # Algolia HN search API - free, no auth needed
            url = "https://hn.algolia.com/api/v1/search_by_date"
            params = {
                "query": "anthropic OR claude ai",
                "tags": "story",
                "hitsPerPage": 15
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for hit in data.get("hits", []):
                published = datetime.now()
                if hit.get("created_at"):
                    try:
                        published = datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
                    except:
                        pass

                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"

                items.append(NewsItem(
                    source=self.SOURCE_CODE,
                    title=hit.get("title", "")[:100],
                    url=story_url,
                    summary=f"{hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments",
                    published=published,
                    content_hash=self._hash_content(hit.get("title", ""), str(hit.get("objectID", "")))
                ))
        except Exception as e:
            print(f"[HN] Error: {e}")

        return items


class GoogleNewsFetcher(SourceFetcher):
    """Fetch from Google News RSS for anthropic/claude"""

    SOURCE_CODE = "GOOG"

    def fetch(self) -> List[NewsItem]:
        items = []

        try:
            # Google News RSS search
            query = "anthropic OR claude ai"
            url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"

            feed = feedparser.parse(url)

            for entry in feed.entries[:15]:
                published = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                # Clean up title (Google adds source at end)
                title = entry.get('title', '')
                if ' - ' in title:
                    title = title.rsplit(' - ', 1)[0]

                items.append(NewsItem(
                    source=self.SOURCE_CODE,
                    title=title[:100],
                    url=entry.get('link', ''),
                    summary=entry.get('summary', '')[:300],
                    published=published,
                    content_hash=self._hash_content(title, entry.get('link', ''))
                ))
        except Exception as e:
            print(f"[GOOG] Error: {e}")

        return items


class NewsFeedAggregator:
    """Combines all sources and handles deduplication"""

    def __init__(self, newsapi_key: str = None):
        self.fetchers = [
            AnthropicBlogFetcher(),
            RedditFetcher(),
            HackerNewsFetcher(),
            GoogleNewsFetcher(),
        ]

        if newsapi_key:
            self.fetchers.append(NewsAPIFetcher(newsapi_key))

    def fetch_all(self) -> List[NewsItem]:
        """Fetch from all sources, deduplicate, return sorted by date"""
        all_items = []
        seen_hashes = set()

        for fetcher in self.fetchers:
            print(f"Fetching from {fetcher.SOURCE_CODE}...")
            items = fetcher.fetch()

            for item in items:
                if item.content_hash not in seen_hashes:
                    seen_hashes.add(item.content_hash)
                    # Normalize datetime to naive (remove timezone)
                    if item.published.tzinfo is not None:
                        item.published = item.published.replace(tzinfo=None)
                    all_items.append(item)

        # Sort by published date, newest first
        all_items.sort(key=lambda x: x.published, reverse=True)

        return all_items


# Quick test
if __name__ == "__main__":
    print("Claude News Feed - Fetcher Test")
    print("="*50)

    aggregator = NewsFeedAggregator()
    items = aggregator.fetch_all()

    print(f"\nFound {len(items)} items:")
    for item in items[:10]:
        print(f"  [{item.source}] {item.title[:50]}...")
