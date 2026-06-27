"""
Claude News Feed - Database Layer
SQLite storage for news items with deduplication.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import json

# Default db location
DB_PATH = Path(__file__).parent / "claude_news.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get database connection, create tables if needed"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE,
            source TEXT,
            title TEXT,
            url TEXT,
            summary TEXT,
            published TIMESTAMP,
            stars INTEGER DEFAULT 0,
            analysis TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_stars ON news_items(stars)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_published ON news_items(published DESC)
    """)

    # Migration: add body column for extracted article text
    try:
        conn.execute("ALTER TABLE news_items ADD COLUMN body TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Migration: track enrichment attempts so we don't keep retrying failures
    try:
        conn.execute("ALTER TABLE news_items ADD COLUMN body_fetched INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Migration: richer body fetch status for diagnostics/retry policy
    try:
        conn.execute("ALTER TABLE news_items ADD COLUMN body_status TEXT DEFAULT 'pending'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE news_items ADD COLUMN body_error TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE news_items ADD COLUMN body_fetched_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    conn.execute("""
        UPDATE news_items
        SET body_status = CASE
            WHEN body_fetched = 1 AND COALESCE(body, '') != '' THEN 'success'
            WHEN body_fetched = 1 THEN 'failed'
            ELSE 'pending'
        END
        WHERE body_status IS NULL OR body_status = 'pending'
    """)

    conn.commit()
    return conn


def add_item(conn: sqlite3.Connection, item: dict) -> bool:
    """
    Add item if not already present.
    Returns True if added, False if duplicate.
    """
    try:
        conn.execute("""
            INSERT INTO news_items (content_hash, source, title, url, summary, published, stars, analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.get('content_hash'),
            item.get('source'),
            item.get('title'),
            item.get('url'),
            item.get('summary'),
            item.get('published'),
            item.get('stars', 0),
            item.get('analysis', '')
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Duplicate hash
        return False


def update_rating(conn: sqlite3.Connection, content_hash: str, stars: int, analysis: str):
    """Update the star rating and analysis for an item"""
    conn.execute("""
        UPDATE news_items
        SET stars = ?, analysis = ?
        WHERE content_hash = ?
    """, (stars, analysis, content_hash))
    conn.commit()


def get_items(
    conn: sqlite3.Connection,
    min_stars: int = 0,
    limit: int = 50,
    include_unrated: bool = True,
    sources: Optional[List[str]] = None,
    query: str = "",
    unread_only: bool = False,
) -> List[dict]:
    """Get items, optionally filtered by rating, source, text, and read state."""
    where = []
    params = []

    if include_unrated:
        where.append("(stars >= ? OR stars = 0)")
    else:
        where.append("stars >= ?")
    params.append(min_stars)

    if sources:
        placeholders = ",".join("?" for _ in sources)
        where.append(f"source IN ({placeholders})")
        params.extend(sources)

    if query:
        like = f"%{query.strip()}%"
        where.append("""
            (
                title LIKE ?
                OR summary LIKE ?
                OR body LIKE ?
                OR analysis LIKE ?
                OR url LIKE ?
            )
        """)
        params.extend([like, like, like, like, like])

    if unread_only:
        where.append("read = 0")

    sql = f"""
        SELECT * FROM news_items
        WHERE {' AND '.join(where)}
        ORDER BY published DESC
        LIMIT ?
    """
    params.append(limit)

    cursor = conn.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def get_unrated_items(conn: sqlite3.Connection, limit: int = 10) -> List[dict]:
    """Get items that haven't been rated yet"""
    cursor = conn.execute("""
        SELECT * FROM news_items
        WHERE stars = 0
        ORDER BY published DESC
        LIMIT ?
    """, (limit,))
    return [dict(row) for row in cursor.fetchall()]


def get_unenriched_items(conn: sqlite3.Connection, limit: int = 50) -> List[dict]:
    """Get items whose article body hasn't been fetched yet."""
    cursor = conn.execute("""
        SELECT * FROM news_items
        WHERE body_status = 'pending' OR body_status IS NULL
        ORDER BY published DESC
        LIMIT ?
    """, (limit,))
    return [dict(row) for row in cursor.fetchall()]


def update_body(conn: sqlite3.Connection, content_hash: str, body: str, error: str = ""):
    """Store extracted article body. Marks body_fetched=1 either way."""
    status = "success" if body else "failed"
    conn.execute("""
        UPDATE news_items
        SET body = ?,
            body_fetched = 1,
            body_status = ?,
            body_error = ?,
            body_fetched_at = CURRENT_TIMESTAMP
        WHERE content_hash = ?
    """, (body or '', status, error or '', content_hash))
    conn.commit()


def get_item_by_hash(conn: sqlite3.Connection, content_hash: str) -> Optional[dict]:
    """Get a specific item by its hash"""
    cursor = conn.execute("""
        SELECT * FROM news_items WHERE content_hash = ?
    """, (content_hash,))
    row = cursor.fetchone()
    return dict(row) if row else None


def mark_read(conn: sqlite3.Connection, content_hash: str):
    """Mark an item as read"""
    conn.execute("""
        UPDATE news_items SET read = 1 WHERE content_hash = ?
    """, (content_hash,))
    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:
    """Get database statistics"""
    stats = {}

    cursor = conn.execute("SELECT COUNT(*) FROM news_items")
    stats['total'] = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM news_items WHERE stars = 0")
    stats['unrated'] = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM news_items WHERE stars >= 4")
    stats['high_priority'] = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM news_items WHERE read = 0")
    stats['unread'] = cursor.fetchone()[0]

    cursor = conn.execute("""
        SELECT body_status, COUNT(*) as cnt
        FROM news_items
        GROUP BY body_status
    """)
    stats['by_body_status'] = {
        (row['body_status'] or 'pending'): row['cnt']
        for row in cursor.fetchall()
    }

    cursor = conn.execute("SELECT source, COUNT(*) as cnt FROM news_items GROUP BY source")
    stats['by_source'] = {row['source']: row['cnt'] for row in cursor.fetchall()}

    return stats


# Quick test
if __name__ == "__main__":
    print("Database Test")
    print("="*50)

    conn = get_connection()

    # Add a test item
    test_item = {
        'content_hash': 'test123',
        'source': 'TEST',
        'title': 'Test Article',
        'url': 'https://example.com',
        'summary': 'This is a test',
        'published': datetime.now().isoformat(),
        'stars': 3,
        'analysis': 'Test analysis'
    }

    added = add_item(conn, test_item)
    print(f"Added: {added}")

    stats = get_stats(conn)
    print(f"Stats: {stats}")

    items = get_items(conn, min_stars=0, limit=5)
    print(f"Items: {len(items)}")
    for item in items:
        print(f"  [{item['source']}] {item['title'][:40]}... ({item['stars']} stars)")
