"""
Claude News Feed - Article Body Extractor
Fetches the URL behind each news item and pulls clean article body text
so the rater has real content (not just a title) to judge.
"""

import requests
import trafilatura
from typing import Optional

USER_AGENT = (
    "Claude-News-Aggregator/1.0 "
    "(personal news feed; low-volume; not for republishing)"
)

DEFAULT_TIMEOUT = 8
MAX_BODY_CHARS = 2500


def _rewrite_url(url: str) -> str:
    """Per-source URL rewrites that improve extraction success."""
    # Reddit blocks the modern www.reddit.com and .json endpoints for scrapers,
    # but old.reddit.com still serves plain HTML happily.
    if "://www.reddit.com/" in url:
        return url.replace("://www.reddit.com/", "://old.reddit.com/")
    if "://reddit.com/" in url:
        return url.replace("://reddit.com/", "://old.reddit.com/")
    return url


def fetch_body(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """
    Fetch a URL and extract the main article body text.
    Returns the extracted text, or None on any failure.
    """
    if not url:
        return None

    url = _rewrite_url(url)

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    # Some sites return non-HTML (PDFs, redirects to login pages, etc.)
    ctype = resp.headers.get("Content-Type", "").lower()
    if "html" not in ctype and "xml" not in ctype:
        return None

    try:
        body = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
        )
    except Exception:
        return None

    if not body:
        return None

    body = body.strip()
    if len(body) > MAX_BODY_CHARS:
        # Cut at a word boundary so we don't end mid-token
        body = body[:MAX_BODY_CHARS].rsplit(" ", 1)[0] + "..."
    return body
