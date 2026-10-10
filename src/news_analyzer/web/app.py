"""FastAPI app: JSON API under /api, server-rendered HTMX pages at /."""

from __future__ import annotations

import sqlite3
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query

from news_analyzer import db, labels
from news_analyzer.authors import author_profile
from news_analyzer.config import get_outlets, get_settings
from news_analyzer.web.serialize import article_dict

LEANING_PATTERN = r"^(-2|-1|0|1|2|na)?$"
PAGE_SIZE = 40

app = FastAPI(title="news_analyzer", docs_url="/api/docs", openapi_url="/api/openapi.json")


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = db.connect(get_settings().db_path)
    try:
        yield conn
    finally:
        conn.close()


class Filters:
    def __init__(self,
                 outlet: str | None = Query(None, max_length=40),
                 topic: str | None = Query(None, max_length=40),
                 leaning: str | None = Query(None, pattern=LEANING_PATTERN),
                 type: str | None = Query(None, max_length=20),
                 offset: int = Query(0, ge=0, le=100_000)):
        self.outlet = outlet or None
        self.topic = topic if topic in labels.TOPICS else None
        self.leaning = leaning or None
        self.type = type if type in labels.ARTICLE_TYPES else None
        self.offset = offset

    def query(self, conn: sqlite3.Connection, limit: int = PAGE_SIZE) -> list[sqlite3.Row]:
        return db.query_feed(conn, outlet=self.outlet, topic=self.topic, leaning=self.leaning,
                             article_type=self.type, limit=limit, offset=self.offset)


def _profile(conn: sqlite3.Connection, author: str | None) -> dict | None:
    s, reg = get_settings(), get_outlets()
    return author_profile(conn, author, min_articles=s.author_min_articles, non_person=reg.non_person_authors)


# ------------------------------------------------------------------------- JSON API
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/meta")
def api_meta():
    return {
        "outlets": {o.id: o.name for o in get_outlets().enabled},
        "topics": labels.TOPICS,
        "article_types": labels.ARTICLE_TYPES,
        "leanings": labels.LEANINGS,
        "axes": labels.AXES,
    }


@app.get("/api/articles")
def api_articles(f: Filters = Depends(), conn: sqlite3.Connection = Depends(get_conn)):
    s, reg = get_settings(), get_outlets()
    return {"items": [article_dict(r, reg, s.timezone) for r in f.query(conn)], "offset": f.offset,
            "page_size": PAGE_SIZE}


@app.get("/api/articles/{article_id}")
def api_article(article_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    row = db.get_article(conn, article_id)
    if row is None:
        raise HTTPException(404, "not found")
    s, reg = get_settings(), get_outlets()
    return {**article_dict(row, reg, s.timezone), "author_profile": _profile(conn, row["author"])}
