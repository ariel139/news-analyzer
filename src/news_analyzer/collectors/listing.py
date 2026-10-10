"""Fallback for outlets without a feed: read article links from a public section page.

Only used when an outlet has no `feeds` but has `listing: {url, link_pattern}`.
Goes through PoliteClient, so robots.txt and rate limits apply.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin

from news_analyzer.collectors.http import PoliteClient, RobotsDisallowed
from news_analyzer.collectors.models import ArticleCandidate
from news_analyzer.collectors.normalize import matches_any, normalize_url
from news_analyzer.config import Outlet

log = logging.getLogger(__name__)


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def parse_listing(html: str, base_url: str, link_pattern: str, outlet: Outlet,
                  *, min_title_len: int = 15) -> list[ArticleCandidate]:
    """Extract (url, anchor text) pairs whose URL matches link_pattern. Pure function."""
    p = _LinkParser()
    p.feed(html)
    rx = re.compile(link_pattern)
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    out: list[ArticleCandidate] = []
    for href, text in p.links:
        url = normalize_url(urljoin(base_url, href))
        if not rx.search(url) or url in seen or len(text) < min_title_len:
            continue
        seen.add(url)
        out.append(ArticleCandidate(outlet=outlet.id, url=url, title=text, published_at=now,
                                    paywalled=matches_any(url, outlet.paywall)))
    return out


def collect_listing(client: PoliteClient, outlet: Outlet) -> list[ArticleCandidate]:
    cfg = outlet.listing or {}
    if not cfg.get("url") or not cfg.get("link_pattern"):
        return []
    try:
        r = client.get(cfg["url"])
    except RobotsDisallowed:
        log.warning("[%s] robots.txt disallows listing page %s", outlet.id, cfg["url"])
        return []
    except Exception as e:
        log.warning("[%s] listing %s failed: %s", outlet.id, cfg["url"], e)
        return []
    items = parse_listing(r.text, cfg["url"], cfg["link_pattern"], outlet)
    log.info("[%s] listing -> %d items", outlet.id, len(items))
    return items
