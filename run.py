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
    ambient = sub.add_parser("ambient", help="Launch Pygame ambient desktop view")
    ambient.add_argument("--windowed", action="store_true", help="Run in a normal-size borderless window")
    ambient.add_argument("--width", type=int, default=1280)
    ambient.add_argument("--height", type=int, default=720)
    ambient.add_argument("--duration", type=float, help="Auto-close after N seconds")
    sub.add_parser("stats", help="Show database stats")
    sub.add_parser("doctor", help="Check local setup and source health")
    sub.add_parser("watchlist", help="Show active watchlist terms")

    watch_hits = sub.add_parser("watch-hits", help="Show recent local items matching watchlist terms")
    watch_hits.add_argument("--limit", type=int, default=100)
    watch_hits.add_argument("--sources", help="Comma-separated source codes")

    vibe = sub.add_parser("vibe", help="Generate or show daily/weekly theme reports")
    vibe.add_argument(
        "period",
        nargs="?",
        default="daily",
        choices=["daily", "weekly", "recent", "latest", "history", "delta"],
    )
    vibe.add_argument("--days", type=int, help="Override lookback days")
    vibe.add_argument("--limit", type=int, default=80)
    vibe.add_argument("--sources", help="Comma-separated source codes")
    vibe.add_argument("--min-stars", type=int, default=0)
    vibe.add_argument("--no-save", action="store_true")

    show = sub.add_parser("show", help="Show feed in terminal")
    show.add_argument("--limit", type=int, default=15)
    show.add_argument("--min-stars", type=int, default=0)
    show.add_argument("--query", "-q", default="", help="Search local title/summary/body/analysis")
    show.add_argument("--sources", help="Comma-separated source codes")
    show.add_argument("--unread", action="store_true", help="Only show unread items")
    show.add_argument("--priority", action="store_true", help="Only show 4+ star rated items")
    show.add_argument("--hidden", action="store_true", help="Include hidden items")

    refresh = sub.add_parser("refresh", help="Fetch, enrich, and rate items")
    refresh.add_argument("--no-rate", action="store_true", help="Fetch/enrich without rating")
    refresh.add_argument("--rate-cap", type=int, help="Max unrated items to rate")
    refresh.add_argument("--enrich-cap", type=int, help="Max items to enrich")
    refresh.add_argument("--full", action="store_true", help="Use high caps for a catch-up refresh")
    refresh.add_argument(
        "--sources",
        help="Comma-separated source codes, e.g. ANTH,HN,GOOG,RDIT,NEWS",
    )

    rerate = sub.add_parser("rerate", help="Rerate existing local items")
    rerate.add_argument("--limit", type=int, default=10)
    rerate.add_argument("--min-stars", type=int, default=0)
    rerate.add_argument("--query", "-q", default="")
    rerate.add_argument("--sources", help="Comma-separated source codes")
    rerate.add_argument("--unread", action="store_true")
    rerate.add_argument("--unrated", action="store_true", help="Only rerate unrated items")
    rerate.add_argument("--priority", action="store_true", help="Only rerate 4+ star rated items")

    mark_read = sub.add_parser("mark-read", help="Mark filtered visible items read")
    mark_read.add_argument("--min-stars", type=int, default=0)
    mark_read.add_argument("--query", "-q", default="")
    mark_read.add_argument("--sources", help="Comma-separated source codes")
    mark_read.add_argument("--priority", action="store_true")

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

    if command == "ambient":
        from ambient import run_ambient
        run_ambient(
            fullscreen=not args.windowed,
            width=args.width,
            height=args.height,
            duration=args.duration,
        )
        return

    if command == "doctor":
        from doctor import run_doctor
        run_doctor()
        return

    if command == "watchlist":
        from watchlist import load_watchlist
        for term in load_watchlist():
            print(term)
        return

    if command == "watch-hits":
        from digest import format_watch_hits, watch_hits
        hits = watch_hits(
            limit=args.limit,
            sources=sorted(parse_sources(args.sources) or []),
        )
        print(format_watch_hits(hits))
        return

    if command == "vibe":
        from digest import (
            VibeDigest,
            format_delta,
            format_history,
            format_report,
            latest_report,
            report_delta,
            report_history,
        )

        if args.period == "latest":
            latest = latest_report()
            if not latest:
                print("No saved vibe reports yet.")
                return
            print(format_report(latest))
            return

        if args.period == "history":
            print(format_history(report_history(limit=args.limit)))
            return

        if args.period == "delta":
            print(format_delta(report_delta()))
            return

        recent = args.period == "recent"
        days = args.days if args.days is not None else (1 if args.period == "daily" else 7)
        digest = VibeDigest()
        result = digest.generate(
            days=days,
            limit=args.limit,
            sources=sorted(parse_sources(args.sources) or []),
            min_stars=args.min_stars,
            save=not args.no_save,
            recent=recent,
        )
        print(format_report(result))
        if result.get("id"):
            print(f"\nSaved vibe report #{result['id']} ({result['item_count']} items).")
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
            hidden=args.hidden,
        )
        print_items(items)
        return

    if command == "rerate":
        feed = ClaudeNewsFeed()
        result = feed.rerate_filtered(
            limit=args.limit,
            min_stars=args.min_stars,
            sources=sorted(parse_sources(args.sources) or []),
            query=args.query,
            unread_only=args.unread,
            unrated_only=args.unrated,
            priority_only=args.priority,
        )
        print(f"Done: {result}")
        return

    if command == "mark-read":
        feed = ClaudeNewsFeed()
        changed = feed.mark_filtered_read(
            min_stars=args.min_stars,
            sources=sorted(parse_sources(args.sources) or []),
            query=args.query,
            priority_only=args.priority,
        )
        print(f"Marked read: {changed}")
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
