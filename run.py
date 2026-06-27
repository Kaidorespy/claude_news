"""
Claude News Feed - Launcher
"""

import argparse
import json
import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))


def configure_console():
    """Prefer UTF-8 output so stars/arrows do not crash on Windows consoles."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def parse_sources(value: str):
    if not value:
        return None
    return {part.strip().upper() for part in value.split(",") if part.strip()}


def print_items(items):
    for item in items:
        stars = "★" * item["stars"] + "☆" * (5 - item["stars"])
        read_marker = " " if item.get("read") else "*"
        print(f"{read_marker}[{item['source']:4}] {item['title'][:45]:45} {stars}")


def build_parser():
    parser = argparse.ArgumentParser(description="Claude News Feed")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ui", help="Launch GUI")
    sub.add_parser("stats", help="Show database stats")
    sub.add_parser("doctor", help="Check local setup and source health")

    show = sub.add_parser("show", help="Show feed in terminal")
    show.add_argument("--limit", type=int, default=15)
    show.add_argument("--min-stars", type=int, default=0)
    show.add_argument("--query", "-q", default="", help="Search local title/summary/body/analysis")
    show.add_argument("--sources", help="Comma-separated source codes")
    show.add_argument("--unread", action="store_true", help="Only show unread items")
    show.add_argument("--priority", action="store_true", help="Only show 4+ star rated items")

    refresh = sub.add_parser("refresh", help="Fetch, enrich, and rate items")
    refresh.add_argument("--no-rate", action="store_true", help="Fetch/enrich without rating")
    refresh.add_argument("--rate-cap", type=int, help="Max unrated items to rate")
    refresh.add_argument("--enrich-cap", type=int, help="Max items to enrich")
    refresh.add_argument("--full", action="store_true", help="Use high caps for a catch-up refresh")
    refresh.add_argument(
        "--sources",
        help="Comma-separated source codes, e.g. ANTH,HN,GOOG,RDIT,NEWS",
    )

    return parser


def main():
    configure_console()
    parser = build_parser()
    args = parser.parse_args()

    command = args.command or "ui"

    if command == "ui":
        from ui import main as ui_main
        ui_main()
        return

    if command == "doctor":
        from doctor import run_doctor
        run_doctor()
        return

    from feed import ClaudeNewsFeed

    if command == "stats":
        feed = ClaudeNewsFeed()
        print(json.dumps(feed.stats(), indent=2))
        return

    if command == "show":
        feed = ClaudeNewsFeed()
        min_stars = 4 if args.priority else args.min_stars
        items = feed.get_feed(
            min_stars=min_stars,
            limit=args.limit,
            sources=sorted(parse_sources(args.sources) or []),
            query=args.query,
            unread_only=args.unread,
            include_unrated=not args.priority,
        )
        print_items(items)
        return

    if command == "refresh":
        sources = parse_sources(args.sources)
        feed = ClaudeNewsFeed(enabled_sources=sources)
        rate_cap = 9999 if args.full else args.rate_cap
        enrich_cap = 9999 if args.full else args.enrich_cap
        result = feed.refresh(
            rate_new=not args.no_rate,
            rate_cap=rate_cap,
            enrich_cap=enrich_cap,
        )
        print(f"Done: {result}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
