from datetime import datetime, timedelta, timezone

import pytest

from news_analyzer import db
from news_analyzer.collectors.models import ArticleCandidate


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
    ], skip_patterns=("/sport",))
    rows = {r["title"]: (r["status"], r["skip_reason"]) for r in conn.execute("SELECT * FROM articles")}
    assert rows == {"רגיל": ("pending", None), "בתשלום": ("paywalled", None), "ספורט": ("skipped", "category")}


def test_pending_queue_newest_first_and_age_limit(conn):
    db.insert_candidates(conn, [cand("https://x/old", "ישן", hours_ago=50),
                                cand("https://x/a", "א", hours_ago=3),
                                cand("https://x/b", "ב", hours_ago=1)])
    assert [r["title"] for r in db.pending_articles(conn, limit=10, max_age_hours=24)] == ["ב", "א"]


def test_feed_query_never_exposes_text_and_purge(conn):
    db.insert_candidates(conn, [cand("https://x/1", "א")])
    aid = conn.execute("SELECT id FROM articles").fetchone()[0]
    db.save_text(conn, aid, "טקסט מלא סודי", "כותב")
    row = db.query_feed(conn)[0]
    assert "analysis_text" not in row.keys()
    assert row["author"] == "כותב"
    # retention: pretend text is 31 days old
    conn.execute("UPDATE articles SET text_fetched_at = ?", (db.iso(db.utcnow() - timedelta(days=31)),))
    assert db.purge_old_text(conn, 30) == 1
    assert conn.execute("SELECT analysis_text FROM articles").fetchone()[0] is None
