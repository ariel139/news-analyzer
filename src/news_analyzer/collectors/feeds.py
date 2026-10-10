"""RSS/Atom collection."""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta, timezone

import feedparser

from news_analyzer.collectors.http import PoliteClient, RobotsDisallowed
from news_analyzer.collectors.models import ArticleCandidate
from news_analyzer.collectors.normalize import make_excerpt, matches_any, normalize_url, strip_html
from news_analyzer.config import Outlet

log = logging.getLogger(__name__)

_TRUE = {"true", "1", "yes"}


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    return None


def parse_feed(content: bytes, outlet: Outlet, *, now: datetime | None = None,
               max_age_hours: int | None = None) -> list[ArticleCandidate]:
    """Turn raw feed bytes into candidates. Pure function - no network."""
    now = now or datetime.now(timezone.utc)
    parsed = feedparser.parse(content)
    out: list[ArticleCandidate] = []
    for e in parsed.entries:
        link, title = e.get("link"), strip_html(e.get("title", ""))
        if not link or not title:
            continue
        # some outlets pre-date scheduled items into the future; clamp so they don't pin the feed top
        published = min(_published(e) or now, now)
        if max_age_hours is not None and now - published > timedelta(hours=max_age_hours):
            continue
        url = normalize_url(link)
        author = strip_html(e.get("author", "")) or None
        paywalled = matches_any(url, outlet.paywall) or str(e.get("ispremium", "")).lower() in _TRUE
        out.append(ArticleCandidate(
            outlet=outlet.id,
            url=url,
            title=title,
            published_at=published,
            author=author,
            excerpt=make_excerpt(e.get("summary", "")),
            tags=[t.get("term") for t in e.get("tags", []) if t.get("term")],
            paywalled=paywalled,
        ))
    return out


def collect_feeds(client: PoliteClient, outlet: Outlet, max_age_hours: int) -> list[ArticleCandidate]:
    items: list[ArticleCandidate] = []
    for feed_url in outlet.feeds:
        try:
            r = client.get(feed_url)
        except RobotsDisallowed:
            log.warning("[%s] robots.txt disallows feed %s", outlet.id, feed_url)
            continue
        except Exception as e:  # network errors must not stop other outlets
            log.warning("[%s] feed %s failed: %s", outlet.id, feed_url, e)
            continue
        batch = parse_feed(r.content, outlet, max_age_hours=max_age_hours)
        log.info("[%s] %s -> %d recent items", outlet.id, feed_url, len(batch))
        items.extend(batch)
    return items
