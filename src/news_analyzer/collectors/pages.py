"""Fetch an article page and extract its main text (for internal analysis only)."""

from __future__ import annotations

import logging

import trafilatura

from news_analyzer.collectors.http import PoliteClient
from news_analyzer.collectors.models import PageText

log = logging.getLogger(__name__)


def extract_page(html: str) -> PageText:
    """Main text + byline from article HTML. Pure function."""
    text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True) or ""
    meta = trafilatura.extract_metadata(html)
    author = meta.author.strip() if meta and meta.author else None
    return PageText(text=text.strip(), author=author or None)


def fetch_page_text(client: PoliteClient, url: str) -> PageText:
    r = client.get(url)  # raises RobotsDisallowed / httpx errors
    return extract_page(r.text)
