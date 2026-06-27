"""
Local diagnostics for Claude News.
"""

import importlib.util
import json
from pathlib import Path

import requests

from config import get_config
from database import get_connection, get_stats


DEPENDENCIES = [
    ("beautifulsoup4", "bs4"),
    ("feedparser", "feedparser"),
    ("python-dotenv", "dotenv"),
    ("requests", "requests"),
    ("trafilatura", "trafilatura"),
]


def _ok(label: str, detail: str = ""):
    suffix = f" - {detail}" if detail else ""
    print(f"[OK]   {label}{suffix}")


def _warn(label: str, detail: str = ""):
    suffix = f" - {detail}" if detail else ""
    print(f"[WARN] {label}{suffix}")


def _fail(label: str, detail: str = ""):
    suffix = f" - {detail}" if detail else ""
    print(f"[FAIL] {label}{suffix}")


def _check_dependencies():
    print("\nDependencies")
    for package, module in DEPENDENCIES:
        if importlib.util.find_spec(module):
            _ok(package)
        else:
            _fail(package, "install with pip install -r requirements.txt")


def _check_database(config):
    print("\nDatabase")
    if config.db_path.exists():
        _ok("database exists", str(config.db_path))
    else:
        _warn("database missing", "it will be created on first run")

    try:
        conn = get_connection(config.db_path)
        stats = get_stats(conn)
        conn.close()
        _ok(
            "database readable",
            f"{stats['total']} items, {stats['high_priority']} priority, {stats['unrated']} unrated",
        )
    except Exception as exc:
        _fail("database readable", str(exc))


def _check_ollama(config):
    print("\nOllama")
    try:
        resp = requests.get(f"{config.ollama_base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        _fail("ollama reachable", str(exc))
        return

    models = [model.get("name", "") for model in data.get("models", [])]
    _ok("ollama reachable", config.ollama_base_url)
    if config.ollama_model in models:
        _ok("configured model available", config.ollama_model)
    else:
        nearby = ", ".join(models[:5]) if models else "no models reported"
        _warn("configured model not listed", f"{config.ollama_model}; available: {nearby}")


def _check_sources(config):
    print("\nSources")
    source_urls = {
        "ANTH": "https://www.anthropic.com/news",
        "RDIT": "https://www.reddit.com/r/ClaudeAI/new.rss",
        "HN": "https://hn.algolia.com/api/v1/search_by_date?query=anthropic&tags=story&hitsPerPage=1",
        "GOOG": "https://news.google.com/rss/search?q=anthropic+OR+claude+ai&hl=en-US&gl=US&ceid=US:en",
    }

    for source in sorted(config.enabled_sources):
        if source == "NEWS":
            if config.newsapi_key:
                _ok("NEWS configured", "NEWSAPI_KEY present")
            else:
                _warn("NEWS disabled", "NEWSAPI_KEY is not set")
            continue

        url = source_urls.get(source)
        if not url:
            _warn(source, "unknown source code")
            continue

        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Claude-News-Doctor/1.0"})
            if resp.status_code < 400:
                _ok(source, f"HTTP {resp.status_code}")
            else:
                _warn(source, f"HTTP {resp.status_code}")
        except requests.exceptions.RequestException as exc:
            _fail(source, str(exc))


def _check_config(config):
    print("Config")
    _ok("enabled sources", ",".join(sorted(config.enabled_sources)))
    _ok("refresh caps", f"rate={config.refresh_rate_cap}, enrich={config.refresh_enrich_cap}")
    _ok("auto refresh", f"{config.auto_refresh_minutes} minutes")
    _ok("ollama model", config.ollama_model)


def run_doctor():
    config = get_config()
    print("Claude News Doctor")
    print("=" * 40)
    _check_config(config)
    _check_dependencies()
    _check_database(config)
    _check_ollama(config)
    _check_sources(config)
