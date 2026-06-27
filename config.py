"""
Central configuration for Claude News.
Values come from .env/environment variables with conservative defaults.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Set

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent


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
    newsapi_key: str = os.getenv("NEWSAPI_KEY", "")
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
                _csv_env("ENABLED_SOURCES", "ANTH,RDIT,HN,GOOG,NEWS"),
            )


def get_config() -> AppConfig:
    return AppConfig()
