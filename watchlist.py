"""
Local subplot/watchlist terms for targeted source capture and vibe reports.
"""

from config import get_config

CONFIG = get_config()

DEFAULT_TERMS = [
    "claude muzzled",
    "claude nerfed",
    "claude censored",
    "claude lobotomized",
    "claude worse",
    "claude code limits",
    "opus slow",
    "sonnet worse",
    "fable rerelease",
    "fable re release",
]


def load_watchlist() -> list:
    """Load local watch terms, falling back to built-in subplot terms."""
    terms = []
    try:
        for line in CONFIG.watchlist_path.read_text(encoding="utf-8").splitlines():
            clean = line.strip()
            if clean and not clean.startswith("#"):
                terms.append(clean)
    except FileNotFoundError:
        pass

    seen = set()
    merged = terms or DEFAULT_TERMS
    unique = []
    for term in merged:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique.append(term)
    return unique
