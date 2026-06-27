"""
Claude News Feed - Main Orchestrator
Ties together fetching, rating, and storage.
"""

from fetcher import NewsFeedAggregator
from database import (
    get_connection, add_item, get_items, get_unrated_items,
    update_rating, get_stats, get_unenriched_items, update_body,
)
from rater import NewsRater, RaterConfig
from enricher import fetch_body
from config import get_config
from pathlib import Path
import json
import sys
import time

CONFIG = get_config()
INTERESTS_PATH = CONFIG.interests_path


def load_interests() -> str:
    """Read the user's free-text interest notes (used to bias the rater)."""
    try:
        return INTERESTS_PATH.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        return ""


def save_interests(text: str):
    """Persist the user's interest notes."""
    INTERESTS_PATH.write_text((text or '').strip(), encoding='utf-8')


class ClaudeNewsFeed:
    """Main feed manager"""

    def __init__(self, db_path: Path = None, newsapi_key: str = None,
                 enabled_sources: set = None):
        self.db_path = db_path or CONFIG.db_path
        self.conn = get_connection(self.db_path)
        self.aggregator = NewsFeedAggregator(
            newsapi_key=newsapi_key if newsapi_key is not None else CONFIG.newsapi_key,
            enabled_sources=enabled_sources or CONFIG.enabled_sources,
        )
        self.rater = NewsRater()

    def refresh(self, rate_new: bool = True, rate_cap: int = None,
                enrich_cap: int = None,
                inter_request_delay: float = None,
                enrich_delay: float = None) -> dict:
        """
        Fetch -> enrich (scrape article body) -> rate.

        - Rates unrated items (not just newly added), up to rate_cap.
        - Enriches items missing body (up to enrich_cap) so the rater
          can judge from real article content, not just titles.
        - Pauses between network calls to be polite.
        """
        print("Refreshing feed...")
        rate_cap = CONFIG.refresh_rate_cap if rate_cap is None else rate_cap
        enrich_cap = CONFIG.refresh_enrich_cap if enrich_cap is None else enrich_cap
        inter_request_delay = (
            CONFIG.refresh_delay_seconds
            if inter_request_delay is None else inter_request_delay
        )
        enrich_delay = CONFIG.enrich_delay_seconds if enrich_delay is None else enrich_delay

        # 1. Fetch
        items = self.aggregator.fetch_all()
        print(f"Fetched {len(items)} items from sources")

        # 2. Add to database (deduplication handled by db)
        added = 0
        for item in items:
            if add_item(self.conn, item.to_dict()):
                added += 1
        print(f"Added {added} new items ({len(items) - added} duplicates skipped)")

        # 3. Enrich: pull article body for anything that doesn't have one yet
        enriched = 0
        enrich_failed = 0
        unenriched = get_unenriched_items(self.conn, limit=enrich_cap)
        if unenriched:
            print(f"\nEnriching {len(unenriched)} items (fetching article bodies)...")
            for i, item in enumerate(unenriched, 1):
                print(f"  [{i}/{len(unenriched)}] {item['title'][:50]}...")
                body = fetch_body(item.get('url', ''))
                update_body(self.conn, item['content_hash'], body or '')
                if body:
                    enriched += 1
                else:
                    enrich_failed += 1
                if i < len(unenriched):
                    time.sleep(enrich_delay)

        # 4. Rate any unrated items (new ones + leftovers from prior failures)
        rated = 0
        rating_failed = 0
        if rate_new:
            interests = load_interests()
            if interests:
                print(f"  (using interest notes: {interests[:60]}...)" if len(interests) > 60
                      else f"  (using interest notes: {interests})")
            unrated = get_unrated_items(self.conn, limit=rate_cap)
            if unrated:
                print(f"\nRating {len(unrated)} unrated items...")
                for i, item in enumerate(unrated, 1):
                    print(f"  [{i}/{len(unrated)}] {item['title'][:50]}...")
                    stars, analysis = self.rater.rate_item(item, interests=interests)
                    update_rating(self.conn, item['content_hash'], stars, analysis)
                    if stars > 0:
                        rated += 1
                    else:
                        rating_failed += 1
                    if i < len(unrated):
                        time.sleep(inter_request_delay)

        return {
            "fetched": len(items),
            "added": added,
            "enriched": enriched,
            "enrich_failed": enrich_failed,
            "rated": rated,
            "rating_failed": rating_failed,
        }

    def get_feed(self, min_stars: int = 0, limit: int = 30,
                 sources: list = None, query: str = "",
                 unread_only: bool = False,
                 include_unrated: bool = True) -> list:
        """Get feed items, optionally filtered by stars"""
        return get_items(
            self.conn,
            min_stars=min_stars,
            limit=limit,
            include_unrated=include_unrated,
            sources=sources,
            query=query,
            unread_only=unread_only,
        )

    def get_high_priority(self, limit: int = 10) -> list:
        """Get 4-5 star items only"""
        return get_items(self.conn, min_stars=4, limit=limit, include_unrated=False)

    def stats(self) -> dict:
        """Get feed statistics"""
        return get_stats(self.conn)


def main():
    """CLI interface"""
    import argparse
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Claude News Feed")
    parser.add_argument("--refresh", action="store_true", help="Fetch new items")
    parser.add_argument("--no-rate", action="store_true", help="Don't rate new items")
    parser.add_argument("--show", type=int, default=10, help="Show N items")
    parser.add_argument("--min-stars", type=int, default=0, help="Filter by minimum stars")
    parser.add_argument("--stats", action="store_true", help="Show stats")

    args = parser.parse_args()

    feed = ClaudeNewsFeed()

    if args.refresh:
        result = feed.refresh(rate_new=not args.no_rate)
        print(f"\nRefresh complete: {result}")

    if args.stats:
        stats = feed.stats()
        print(f"\nStats: {json.dumps(stats, indent=2)}")

    # Show feed
    items = feed.get_feed(min_stars=args.min_stars, limit=args.show)
    print(f"\n{'='*60}")
    print(f"FEED ({len(items)} items, min {args.min_stars} stars)")
    print(f"{'='*60}")

    for item in items:
        stars = "★" * item['stars'] + "☆" * (5 - item['stars'])
        print(f"[{item['source']:4}] {item['title'][:45]:45} {stars}")

        # Show analysis if available
        if item['analysis']:
            try:
                analysis = json.loads(item['analysis'])
                if analysis.get('tldr'):
                    print(f"       └─ {analysis['tldr']}")
            except:
                pass


if __name__ == "__main__":
    main()
