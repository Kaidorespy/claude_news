"""
Theme and vibe extraction for Claude News.

This intentionally looks across many noisy items for recurring narratives,
subplots, weak signals, and community mood rather than summarizing one link.
"""

import json
from collections import Counter
from typing import List, Optional

import requests

from config import get_config
from database import (
    get_connection,
    get_latest_items_for_digest,
    get_latest_vibe_report,
    get_recent_items_for_digest,
    save_vibe_report,
)
from watchlist import load_watchlist

CONFIG = get_config()


class DigestError(Exception):
    """Digest generation failed."""


class VibeDigest:
    """Generate daily/weekly vibe reports from local feed items."""

    PROMPT = """You are analyzing a noisy local news/social feed about Anthropic, Claude, Claude Code, and adjacent AI communities.

Your job is not to summarize articles one-by-one. Your job is to infer the emergent "vibe":
- recurring anxieties
- community unrest
- subplot narratives
- weak signals that may become stories
- watchlist-matching subplot evidence
- disagreements between official news and user chatter
- what changed in mood compared with a normal week, if inferable

Be careful:
- Only claim themes supported by multiple items or strong evidence.
- If a theme is speculative, say so.
- Do not invent facts outside the provided feed items.
- Treat Reddit/HN posts as community sentiment, not verified fact.

Return exact JSON:
{{
  "headline": "<short name for the overall vibe>",
  "mood": "<1-3 sentence read of the overall mood>",
  "top_themes": [
    {{
      "name": "<theme name>",
      "summary": "<what people seem to be reacting to>",
      "evidence": ["<short item title/source>", "<short item title/source>"],
      "confidence": "low|medium|high"
    }}
  ],
  "subplots": [
    {{
      "name": "<subplot name>",
      "summary": "<why it matters or why it may grow>",
      "evidence": ["<short item title/source>"],
      "confidence": "low|medium|high"
    }}
  ],
  "watch_next": ["<what to watch for next>"],
  "noise": ["<things that look overrepresented, repetitive, or low-signal>"],
  "one_line": "<a compact daily/weekly vibe sentence>"
}}

PERIOD: {period}
ITEM COUNT: {item_count}
SOURCE COUNTS: {source_counts}
STAR COUNTS: {star_counts}
WATCHLIST TERMS: {watchlist_terms}

FEED ITEMS:
{items_text}

JSON response:"""

    def __init__(self):
        self.config = CONFIG

    def _call_ollama(self, prompt: str) -> str:
        url = f"{self.config.ollama_base_url}/api/generate"
        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.35,
                "num_predict": 1600,
            },
        }
        resp = requests.post(url, json=payload, timeout=self.config.ollama_timeout)
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _parse_json(self, response: str) -> dict:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start < 0 or end <= start:
            raise DigestError("no JSON object in digest response")
        try:
            return json.loads(response[start:end])
        except json.JSONDecodeError as exc:
            raise DigestError(f"invalid JSON: {exc}")

    def _format_items(self, items: List[dict]) -> str:
        lines = []
        for idx, item in enumerate(items, 1):
            analysis = {}
            try:
                analysis = json.loads(item.get("analysis") or "{}")
            except json.JSONDecodeError:
                pass
            tldr = analysis.get("tldr") or analysis.get("first_impressions") or ""
            summary = (item.get("summary") or "").strip()
            body = (item.get("body") or "").strip()
            context = summary or body[:240] or tldr
            lines.append(
                f"{idx}. [{item.get('source', 'UNK')}] "
                f"{item.get('title', 'No title')} "
                f"(stars={item.get('stars', 0)}, date={item.get('published', '')})\n"
                f"   context: {context[:350]}"
            )
        return "\n".join(lines)

    def generate(
        self,
        days: int = 1,
        limit: int = 80,
        sources: Optional[List[str]] = None,
        min_stars: int = 0,
        save: bool = True,
        recent: bool = False,
        fallback_min_items: int = 8,
    ) -> dict:
        period = "recent" if recent else "daily" if days <= 1 else "weekly" if days <= 7 else f"{days}-day"
        conn = get_connection(self.config.db_path)
        if recent:
            items = get_latest_items_for_digest(
                conn,
                limit=limit,
                sources=sources,
                min_stars=min_stars,
            )
        else:
            items = get_recent_items_for_digest(
                conn,
                days=days,
                limit=limit,
                sources=sources,
                min_stars=min_stars,
            )
            if days <= 1 and len(items) < fallback_min_items:
                items = get_latest_items_for_digest(
                    conn,
                    limit=limit,
                    sources=sources,
                    min_stars=min_stars,
                )
                period = "daily/recent"
        if not items:
            conn.close()
            return {
                "period": period,
                "days": days,
                "item_count": 0,
                "report": {
                    "headline": "No signal",
                    "mood": "No matching feed items were found for this period.",
                    "top_themes": [],
                    "subplots": [],
                    "watch_next": [],
                    "noise": [],
                    "one_line": "No local signal for this window.",
                },
            }

        source_counts = dict(Counter(item.get("source", "UNK") for item in items))
        star_counts = dict(Counter(str(item.get("stars", 0)) for item in items))
        prompt = self.PROMPT.format(
            period=period,
            item_count=len(items),
            source_counts=json.dumps(source_counts, sort_keys=True),
            star_counts=json.dumps(star_counts, sort_keys=True),
            watchlist_terms=", ".join(load_watchlist()[:20]),
            items_text=self._format_items(items),
        )
        response = self._call_ollama(prompt)
        report = self._parse_json(response)

        result = {
            "period": period,
            "days": days,
            "item_count": len(items),
            "report": report,
        }

        if save:
            report_id = save_vibe_report(
                conn,
                period=period,
                days=days,
                item_count=len(items),
                report_json=json.dumps(report),
            )
            result["id"] = report_id

        conn.close()
        return result


def latest_report(period: str = None) -> Optional[dict]:
    conn = get_connection(CONFIG.db_path)
    row = get_latest_vibe_report(conn, period=period)
    conn.close()
    if not row:
        return None
    row["report"] = json.loads(row["report_json"])
    return row


def format_report(result: dict) -> str:
    report = result.get("report", result)
    lines = [
        f"{report.get('headline', 'Vibe Report')}",
        "=" * 60,
        report.get("mood", ""),
        "",
    ]

    def add_section(title, rows):
        if not rows:
            return
        lines.append(title)
        lines.append("-" * len(title))
        for row in rows:
            if isinstance(row, dict):
                confidence = row.get("confidence")
                suffix = f" [{confidence}]" if confidence else ""
                lines.append(f"* {row.get('name', 'Theme')}{suffix}: {row.get('summary', '')}")
                evidence = row.get("evidence") or []
                if evidence:
                    lines.append(f"  evidence: {'; '.join(evidence[:3])}")
            else:
                lines.append(f"* {row}")
        lines.append("")

    add_section("Top Themes", report.get("top_themes"))
    add_section("Subplots", report.get("subplots"))
    add_section("Watch Next", report.get("watch_next"))
    add_section("Noise", report.get("noise"))
    if report.get("one_line"):
        lines.append(f"One line: {report['one_line']}")
    return "\n".join(lines).strip()
