"""SQLite storage: schema, dedup on insert, queue and feed queries.

Article status flow:
    pending  -> done | failed | skipped
    paywalled (terminal; never fetched or analyzed)
    skipped   (terminal; reason in skip_reason: category | robots | short_text | fetch_error)

`analysis_text` is internal input for the LLM. The web server (web/server/db.ts) reads this DB read-only
and never selects it.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from news_analyzer.collectors.models import ArticleCandidate
from news_analyzer.collectors.normalize import matches_any, title_key

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY,
    outlet          TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    title_key       TEXT NOT NULL,
    author          TEXT,
    published_at    TEXT NOT NULL,          -- ISO-8601 UTC
    collected_at    TEXT NOT NULL,
    excerpt         TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '[]',
    analysis_text   TEXT,                   -- INTERNAL ONLY: never displayed
    text_fetched_at TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    skip_reason     TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_articles_outlet_title ON articles(outlet, title_key);
CREATE INDEX IF NOT EXISTS ix_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS ix_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS ix_articles_author ON articles(author);

CREATE TABLE IF NOT EXISTS analyses (
    article_id      INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    duration_sec    REAL,
    article_type    TEXT NOT NULL,
    topic           TEXT NOT NULL,
    favored_side    TEXT,                   -- left/right/none; NULL for prompt v1 rows
    security_score  INTEGER, security_conf TEXT,
    religion_score  INTEGER, religion_conf TEXT,
    economy_score   INTEGER, economy_conf  TEXT,
    tone_score      INTEGER, tone_conf     TEXT,
    overall_score   INTEGER, overall_conf  TEXT,
    explanation     TEXT NOT NULL,
    evidence        TEXT NOT NULL DEFAULT '[]',
    summary         TEXT NOT NULL,
    raw_json        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_analyses_topic ON analyses(topic);
CREATE INDEX IF NOT EXISTS ix_analyses_type ON analyses(article_type);
CREATE INDEX IF NOT EXISTS ix_analyses_overall ON analyses(overall_score);

CREATE TABLE IF NOT EXISTS analysis_failures (
    id          INTEGER PRIMARY KEY,
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    model       TEXT NOT NULL,
    attempt     INTEGER NOT NULL,
    error       TEXT NOT NULL,
    raw_output  TEXT
);
"""

AXES = ("security", "religion", "economy", "tone", "overall")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # web reads while the worker writes
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring databases created by older versions up to SCHEMA (CREATE IF NOT EXISTS won't add columns)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(analyses)")}
    if "favored_side" not in cols:  # v1 -> v2
        conn.execute("ALTER TABLE analyses ADD COLUMN favored_side TEXT")
        conn.commit()


@contextmanager
def open_db(path: Path | str) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- ingest
def insert_candidates(conn: sqlite3.Connection, items: list[ArticleCandidate],
                      skip_patterns: tuple[str, ...] = ()) -> int:
    """Insert new articles, ignoring duplicates (same URL, or same outlet + title). Returns #inserted."""
    now = iso(utcnow())
    inserted = 0
    for c in items:
        if c.paywalled:
            status, reason = "paywalled", None
        elif matches_any(c.url, skip_patterns):
            status, reason = "skipped", "category"
        else:
            status, reason = "pending", None
        cur = conn.execute(
            """INSERT OR IGNORE INTO articles
               (outlet, url, title, title_key, author, published_at, collected_at, excerpt, tags, status, skip_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (c.outlet, c.url, c.title, title_key(c.title), c.author, iso(c.published_at), now,
             c.excerpt, json.dumps(c.tags, ensure_ascii=False), status, reason),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


# --------------------------------------------------------------------------- analysis queue
def pending_articles(conn: sqlite3.Connection, limit: int, max_age_hours: int) -> list[sqlite3.Row]:
    since = iso(utcnow() - timedelta(hours=max_age_hours))
    return conn.execute(
        """SELECT * FROM articles WHERE status = 'pending' AND published_at >= ?
           ORDER BY published_at DESC LIMIT ?""",
        (since, limit),
    ).fetchall()


def save_text(conn: sqlite3.Connection, article_id: int, text: str, author: str | None) -> None:
    conn.execute(
        """UPDATE articles SET analysis_text = ?, text_fetched_at = ?,
           author = COALESCE(author, ?) WHERE id = ?""",
        (text, iso(utcnow()), author, article_id),
    )
    conn.commit()


def set_status(conn: sqlite3.Connection, article_id: int, status: str, reason: str | None = None) -> None:
    conn.execute("UPDATE articles SET status = ?, skip_reason = ? WHERE id = ?", (status, reason, article_id))
    conn.commit()


def bump_attempts(conn: sqlite3.Connection, article_id: int) -> int:
    conn.execute("UPDATE articles SET attempts = attempts + 1 WHERE id = ?", (article_id,))
    conn.commit()
    return conn.execute("SELECT attempts FROM articles WHERE id = ?", (article_id,)).fetchone()[0]


def save_analysis(conn: sqlite3.Connection, article_id: int, row: dict) -> None:
    """row: flat dict with keys matching the analyses columns (except article_id)."""
    cols = ["article_id", *row.keys()]
    conn.execute(
        f"INSERT OR REPLACE INTO analyses ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [article_id, *row.values()],
    )
    conn.execute("UPDATE articles SET status = 'done', skip_reason = NULL WHERE id = ?", (article_id,))
    conn.commit()


def log_failure(conn: sqlite3.Connection, article_id: int, model: str, attempt: int,
                error: str, raw_output: str | None) -> None:
    conn.execute(
        """INSERT INTO analysis_failures (article_id, created_at, model, attempt, error, raw_output)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (article_id, iso(utcnow()), model, attempt, error[:2000], (raw_output or "")[:20000]),
    )
    conn.commit()


# --------------------------------------------------------------------------- maintenance
def purge_old_text(conn: sqlite3.Connection, retention_days: int) -> int:
    """Drop stored article text after the retention period; metadata and ratings stay."""
    cutoff = iso(utcnow() - timedelta(days=retention_days))
    cur = conn.execute(
        "UPDATE articles SET analysis_text = NULL WHERE analysis_text IS NOT NULL AND text_fetched_at < ?",
        (cutoff,),
    )
    conn.commit()
    return cur.rowcount


def stats(conn: sqlite3.Connection) -> dict:
    by_status = dict(conn.execute("SELECT status, COUNT(*) FROM articles GROUP BY status").fetchall())
    by_outlet = dict(conn.execute("SELECT outlet, COUNT(*) FROM articles GROUP BY outlet").fetchall())
    failures = conn.execute("SELECT COUNT(*) FROM analysis_failures").fetchone()[0]
    return {"by_status": by_status, "by_outlet": by_outlet, "failure_log_rows": failures}
