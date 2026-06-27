"""
Claude News Feed - Launcher
Quick way to run the feed.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))


def configure_console():
    """Prefer UTF-8 output so stars/arrows do not crash on Windows consoles."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main():
    configure_console()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "ui":
            from ui import main as ui_main
            ui_main()

        elif cmd == "refresh":
            from feed import ClaudeNewsFeed
            feed = ClaudeNewsFeed()
            result = feed.refresh(rate_new="--no-rate" not in sys.argv)
            print(f"Done: {result}")

        elif cmd == "show":
            from feed import ClaudeNewsFeed
            feed = ClaudeNewsFeed()
            items = feed.get_feed(limit=15)
            for item in items:
                stars = "★" * item['stars'] + "☆" * (5 - item['stars'])
                print(f"[{item['source']:4}] {item['title'][:45]:45} {stars}")

        elif cmd == "stats":
            from feed import ClaudeNewsFeed
            feed = ClaudeNewsFeed()
            import json
            print(json.dumps(feed.stats(), indent=2))

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python run.py [ui|refresh|show|stats]")

    else:
        # Default: launch UI
        from ui import main as ui_main
        ui_main()


if __name__ == "__main__":
    main()
