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

## Sources

- `ANTH` - Anthropic official news page
- `RDIT` - Reddit RSS for r/anthropic, r/ClaudeAI, and r/LocalLLaMA
- `HN` - Hacker News Algolia search
- `GOOG` - Google News RSS
- `NEWS` - NewsAPI, enabled when `NEWSAPI_KEY` is configured

## Files

```text
claude_news/
|-- run.py            # Launcher
|-- ui.py             # Tkinter UI
|-- feed.py           # Main orchestrator
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
python run.py refresh   # Fetch + rate new items
python run.py refresh --no-rate
python run.py show      # Show feed in terminal
python run.py stats     # Show database stats
```

## Config

Copy `.env.example` to `.env` and adjust values as needed.

```text
NEWSAPI_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3-coder:480b-cloud
OLLAMA_TEMPERATURE=0.3
OLLAMA_TIMEOUT=120
```

## Next Ideas

- Source toggles in the UI
- Search and saved filters
- Better cross-source deduplication
- A compact "priority only" mode
- System tray support
- True always-behind Windows behavior
