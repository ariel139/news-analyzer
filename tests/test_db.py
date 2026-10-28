from datetime import datetime, timedelta, timezone

import pytest

from news_analyzer import db
from news_analyzer.collectors.models import ArticleCandidate
from news_analyzer.triage import SkipRules


def cand(url, title="כותרת", outlet="ynet", hours_ago=1, **kw):
    return ArticleCandidate(outlet=outlet, url=url, title=title,
                            published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago), **kw)


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


def test_dedup_by_url_and_by_outlet_title(conn):
    n = db.insert_candidates(conn, [
        cand("https://x/1", "כותרת א"),
        cand("https://x/1", "כותרת א"),          # same URL
        cand("https://x/2", "כותרת  א!"),         # same outlet + same title key
        cand("https://y/2", "כותרת א", outlet="walla"),  # other outlet: kept
    ])
    assert n == 2
    assert db.insert_candidates(conn, [cand("https://x/1", "כותרת א")]) == 0


def test_initial_status(conn):
    db.insert_candidates(conn, [
        cand("https://x/news/1", "רגיל"),
        cand("https://x/news/2", "בתשלום", paywalled=True),
        cand("https://x/sport/3", "ספורט"),
    ], skip_rules=SkipRules(url_patterns=("/sport",)))
    rows = {r["title"]: (r["status"], r["skip_reason"]) for r in conn.execute("SELECT * FROM articles")}
    assert rows == {"רגיל": ("pending", None), "בתשלום": ("paywalled", None), "ספורט": ("skipped", "category")}


def test_skip_rules_reapplied_to_pending_only(conn):
    db.insert_candidates(conn, [cand("https://x/1", "תחזית", tags=["מזג אוויר"]),
                                cand("https://x/2", "רגיל"),
                                cand("https://x/3", "נותח", tags=["מזג אוויר"])])
    conn.execute("UPDATE articles SET status = 'done' WHERE title = 'נותח'")
    assert db.skip_pending_by_rules(conn, SkipRules(tags=("מזג אוויר",))) == 1
    rows = {r["title"]: (r["status"], r["skip_reason"]) for r in conn.execute("SELECT * FROM articles")}
    assert rows == {"תחזית": ("skipped", "category"), "רגיל": ("pending", None), "נותח": ("done", None)}


def test_pending_queue_newest_first_and_age_limit(conn):
    db.insert_candidates(conn, [cand("https://x/old", "ישן", hours_ago=50),
                                cand("https://x/a", "א", hours_ago=3),
                                cand("https://x/b", "ב", hours_ago=1)])
    assert [r["title"] for r in db.pending_articles(conn, limit=10, max_age_hours=24)] == ["ב", "א"]


def test_save_text_and_purge(conn):
    db.insert_candidates(conn, [cand("https://x/1", "א")])
    aid = conn.execute("SELECT id FROM articles").fetchone()[0]
    db.save_text(conn, aid, "טקסט מלא סודי", "כותב")
    assert conn.execute("SELECT author FROM articles").fetchone()[0] == "כותב"
    # retention: pretend text is 31 days old
    conn.execute("UPDATE articles SET text_fetched_at = ?", (db.iso(db.utcnow() - timedelta(days=31)),))
    assert db.purge_old_text(conn, 30) == 1
    assert conn.execute("SELECT analysis_text FROM articles").fetchone()[0] is None


def test_v1_database_gets_favored_side_column(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    v1_schema = db.SCHEMA.replace(
        "    favored_side    TEXT,                   -- left/right/none; NULL for prompt v1 rows\n", "")
    assert v1_schema != db.SCHEMA
    old.executescript(v1_schema)
    old.execute("PRAGMA user_version = 1")
    old.close()
    c = db.connect(path)
    assert "favored_side" in {r["name"] for r in c.execute("PRAGMA table_info(analyses)")}
    assert c.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    c.close()
    db.connect(path).close()  # second open is a no-op
