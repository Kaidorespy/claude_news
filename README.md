# Claude News Feed

A cyberpunk terminal-style news aggregator for Anthropic/Claude updates.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Launch the UI
python run.py

# Or use the CLI
python run.py refresh
python run.py show
python run.py stats
python run.py doctor
```

## Features

- Desktop Tkinter feed window with Dracula-inspired terminal styling
- Star rating system, judged by a local Ollama model
- Click star levels to filter the feed
- Click article titles to open the original source
- Click stars to inspect the LLM analysis
- Interest notes that bias future ratings
- Article body enrichment before rating
- Hourly auto-refresh while the UI is open
- Source toggles for filtering and targeted refreshes
- Local search, unread-only, and priority-only filters
- Rerate existing items after changing interest notes
- Mark filtered sets read and hide/archive low-signal items
- Daily/weekly vibe reports that extract themes, subplots, unrest, weak signals, and noise
- Watchlist-driven Reddit search capture for emerging subplot terms
- Optional Pygame ambient desktop view with RSS rail and animated newspaper panels
- `doctor` command for local diagnostics

## Sources

- `ANTH` - Anthropic official news page
- `RDIT` - Reddit RSS for r/anthropic, r/ClaudeAI, and r/LocalLLaMA
- `RDSR` - Watchlist-driven Reddit search RSS
- `HN` - Hacker News Algolia search
- `GOOG` - Google News RSS
- `NEWS` - NewsAPI, enabled when `NEWSAPI_KEY` is configured

## Files

```text
claude_news/
|-- run.py            # Launcher
|-- ui.py             # Tkinter UI
|-- feed.py           # Main orchestrator
|-- config.py         # Environment-backed settings
|-- doctor.py         # Local diagnostics
|-- fetcher.py        # Source fetchers
|-- enricher.py       # Article body extraction
|-- rater.py          # Ollama rating
|-- database.py       # SQLite storage
|-- requirements.txt  # Python dependencies
|-- .env.example      # Optional local config template
`-- claude_news.db    # Local database
```

## Commands

```bash
python run.py ui        # Launch GUI
python run.py ambient   # Fullscreen ambient view
python run.py ambient --windowed
python run.py refresh   # Fetch + rate new items
python run.py refresh --no-rate
python run.py refresh --sources ANTH,HN,GOOG
python run.py refresh --full
python run.py show      # Show feed in terminal
python run.py show --limit 25 --min-stars 4
python run.py show --query "claude code" --sources HN,RDIT
python run.py show --priority --unread
python run.py rerate --unrated --limit 10
python run.py rerate --query "claude code" --sources HN,RDIT --limit 5
python run.py mark-read --priority
python run.py vibe daily
python run.py vibe weekly
python run.py vibe recent
python run.py vibe latest
python run.py vibe history
python run.py vibe delta
python run.py watchlist
python run.py watch-hits
python run.py refresh --sources RDSR --no-rate
python run.py stats     # Show database stats
python run.py doctor    # Check setup/source health
```

## Config

Copy `.env.example` to `.env` and adjust values as needed.
Copy `watchlist.example.txt` to `watchlist.txt` to customize subplot search terms.

```text
NEWSAPI_KEY=
REDDIT_RSS_USER=
REDDIT_RSS_FEED=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3-coder:480b-cloud
OLLAMA_TEMPERATURE=0.3
OLLAMA_TIMEOUT=120
ENABLED_SOURCES=ANTH,RDIT,HN,GOOG,NEWS
REFRESH_RATE_CAP=10
REFRESH_ENRICH_CAP=20
REFRESH_DELAY_SECONDS=1.5
ENRICH_DELAY_SECONDS=2.0
AUTO_REFRESH_MINUTES=60
```

## Next Ideas

- Source toggles in the UI
- Search and saved filters
- Better cross-source deduplication
- A compact "priority only" mode
- System tray support
- True always-behind Windows behavior
