"""
Central configuration for Claude News.
Values come from .env/environment variables with conservative defaults.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Set

def app_root() -> Path:
    """Return the folder that should hold local config and data files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = app_root()

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _csv_env(name: str, default: str) -> Set[str]:
    raw = os.getenv(name, default)
    return {part.strip().upper() for part in raw.split(",") if part.strip()}


@dataclass(frozen=True)
class AppConfig:
    db_path: Path = ROOT / "claude_news.db"
    interests_path: Path = ROOT / "interests.txt"
    watchlist_path: Path = ROOT / "watchlist.txt"
    newsapi_key: str = os.getenv("NEWSAPI_KEY", "")
    reddit_rss_user: str = os.getenv("REDDIT_RSS_USER", "")
    reddit_rss_feed: str = os.getenv("REDDIT_RSS_FEED", "")
    enabled_sources: Set[str] = None
    refresh_rate_cap: int = _int_env("REFRESH_RATE_CAP", 10)
    refresh_enrich_cap: int = _int_env("REFRESH_ENRICH_CAP", 20)
    refresh_delay_seconds: float = _float_env("REFRESH_DELAY_SECONDS", 1.5)
    enrich_delay_seconds: float = _float_env("ENRICH_DELAY_SECONDS", 2.0)
    auto_refresh_minutes: int = _int_env("AUTO_REFRESH_MINUTES", 60)
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3-coder:480b-cloud")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_temperature: float = _float_env("OLLAMA_TEMPERATURE", 0.3)
    ollama_timeout: int = _int_env("OLLAMA_TIMEOUT", 120)

    def __post_init__(self):
        if self.enabled_sources is None:
            object.__setattr__(
                self,
                "enabled_sources",
                _csv_env("ENABLED_SOURCES", "ANTH,RDIT,RDSR,HN,GOOG,NEWS"),
            )


def get_config() -> AppConfig:
    return AppConfig()
