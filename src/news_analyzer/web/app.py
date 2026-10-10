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
                 analyzed: bool = Query(False),
                 q: str | None = Query(None, max_length=80),
                 offset: int = Query(0, ge=0, le=100_000)):
        self.outlet = outlet or None
        self.topic = topic if topic in labels.TOPICS else None
        self.leaning = leaning or None
        self.type = type if type in labels.ARTICLE_TYPES else None
        self.analyzed = analyzed
        self.q = (q or "").strip() or None
        self.offset = offset

    def query(self, conn: sqlite3.Connection, limit: int = PAGE_SIZE) -> list[sqlite3.Row]:
        return db.query_feed(conn, outlet=self.outlet, topic=self.topic, leaning=self.leaning,
                             article_type=self.type, analyzed_only=self.analyzed, q=self.q,
                             limit=limit, offset=self.offset)


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


# ------------------------------------------------------------------------- HTML (HTMX)
from datetime import date, datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from fastapi import Request  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


def reltime(dt: datetime) -> str:
    """'לפני 5 דק׳' for recent items, otherwise a local date."""
    minutes = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if minutes < 1:
        return "עכשיו"
    if minutes < 60:
        return f"לפני {minutes} דק׳"
    if minutes < 24 * 60:
        h = minutes // 60
        return "לפני שעה" if h == 1 else f"לפני {h} שעות"
    return dt.strftime("%d.%m %H:%M")


WEEKDAYS = ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")  # date.weekday() order


MONTHS = ("ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר",
          "נובמבר", "דצמבר")
# Topics offered in the section bar. Sports/culture/other are mostly skipped by the analyzer.
NAV_TOPICS = [k for k in labels.TOPICS if k not in ("sports", "culture", "other")]
FEATURED_COUNT = 5


def today_he() -> str:
    d = datetime.now(ZoneInfo(get_settings().timezone)).date()
    return f"יום {WEEKDAYS[d.weekday()]}, {d.day} ב{MONTHS[d.month - 1]} {d.year}"


def daylabel(d: date) -> str:
    """Feed section heading: 'היום', 'אתמול', or 'יום חמישי, 8.10'."""
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    if d == today:
        return "היום"
    if d == today - timedelta(days=1):
        return "אתמול"
    return f"יום {WEEKDAYS[d.weekday()]}, {d.day}.{d.month}"


def marker_pct(score: int, lo: int, hi: int) -> float:
    return round((score - lo) / (hi - lo) * 100, 1)


# Outlet site icons, vendored once into static/logos/<outlet id>.png so visitors never hit the outlets.
LOGOS = {p.stem for p in (HERE / "static" / "logos").glob("*.png")}


def logo_url(outlet_id: str) -> str | None:
    return f"/static/logos/{outlet_id}.png" if outlet_id in LOGOS else None


templates.env.filters["reltime"] = reltime
templates.env.filters["daylabel"] = daylabel
templates.env.globals.update(labels=labels, marker_pct=marker_pct, logo_url=logo_url, today_he=today_he,
                             nav_topics=NAV_TOPICS)


def _feed_ctx(request: Request, f: Filters, conn: sqlite3.Connection, after_day: str | None = None) -> dict:
    """`after_day` is the last day heading already on the page, so "load more" doesn't repeat it."""
    s, reg = get_settings(), get_outlets()
    items = [article_dict(r, reg, s.timezone) for r in f.query(conn)]
    params = {k: v for k, v in {"outlet": f.outlet, "topic": f.topic, "leaning": f.leaning, "type": f.type,
                                "analyzed": "1" if f.analyzed else None, "q": f.q}.items() if v}
    last_day = items[-1]["published_local"].date().isoformat() if items else after_day
    return {"request": request, "items": items, "filters": params, "after_day": after_day,
            "last_day": last_day, "next_offset": f.offset + PAGE_SIZE if len(items) == PAGE_SIZE else None}


def _overview(conn: sqlite3.Connection) -> dict:
    now = datetime.now(timezone.utc)
    ov = db.feed_overview(conn, outlets_since=db.iso(now - timedelta(hours=24)),
                          topics_since=db.iso(now - timedelta(days=7)))
    ov["last_collected_dt"] = datetime.fromisoformat(ov["last_collected"]) if ov["last_collected"] else None
    return ov


@app.get("/", response_class=HTMLResponse)
def page_index(request: Request, f: Filters = Depends(), conn: sqlite3.Connection = Depends(get_conn)):
    ctx = _feed_ctx(request, f, conn)
    ctx["outlets"] = {o.id: o.name for o in get_outlets().enabled}
    by_status = db.stats(conn)["by_status"]
    ctx["stats"] = {"total": sum(by_status.values()), "analyzed": by_status.get("done", 0),
                    "outlets": len(ctx["outlets"])}
    ctx["overview"] = _overview(conn)
    if not ctx["filters"] and f.offset == 0:  # lead section only on the unfiltered front page
        s, reg = get_settings(), get_outlets()
        ctx["featured"] = [article_dict(r, reg, s.timezone)
                           for r in db.query_feed(conn, analyzed_only=True, limit=FEATURED_COUNT)]
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/fragments/feed", response_class=HTMLResponse)
def frag_feed(request: Request, f: Filters = Depends(), conn: sqlite3.Connection = Depends(get_conn),
              after_day: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    return templates.TemplateResponse(request, "_feed_items.html", _feed_ctx(request, f, conn, after_day))


@app.get("/fragments/new", response_class=HTMLResponse)
def frag_new(request: Request, since: str = Query(..., max_length=40),
             conn: sqlite3.Connection = Depends(get_conn)):
    """Polled by the index page: how many articles were collected since it was rendered."""
    try:
        datetime.fromisoformat(since)
    except ValueError:
        raise HTTPException(422, "invalid since")
    return templates.TemplateResponse(request, "_new_banner.html",
                                      {"n": db.count_collected_after(conn, since)})


@app.get("/fragments/article/{article_id}", response_class=HTMLResponse)
def frag_article(request: Request, article_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    row = db.get_article(conn, article_id)
    if row is None:
        raise HTTPException(404, "not found")
    s, reg = get_settings(), get_outlets()
    return templates.TemplateResponse(request, "_panel.html", {
        "a": article_dict(row, reg, s.timezone), "profile": _profile(conn, row["author"])})


@app.get("/article/{article_id}", response_class=HTMLResponse)
def page_article(request: Request, article_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    row = db.get_article(conn, article_id)
    if row is None:
        raise HTTPException(404, "not found")
    s, reg = get_settings(), get_outlets()
    return templates.TemplateResponse(request, "article.html", {
        "a": article_dict(row, reg, s.timezone), "profile": _profile(conn, row["author"])})


@app.get("/methodology", response_class=HTMLResponse)
def page_methodology(request: Request):
    s = get_settings()
    return templates.TemplateResponse(request, "methodology.html", {
        "model": s.llm_model, "min_author": s.author_min_articles,
        "outlets": get_outlets().outlets, "retention": s.text_retention_days})
