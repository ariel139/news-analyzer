"""Pure helpers for URLs, titles and short excerpts."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|ref$|partner$|from$)", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_url(url: str) -> str:
    """Canonical form used for dedup: https, lowercase host, no fragment/tracking params/trailing slash."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, urlencode(query), ""))


def title_key(title: str) -> str:
    """Loose title fingerprint: same outlet + same key = duplicate (e.g. the same item in two feeds)."""
    t = _PUNCT_RE.sub(" ", title)
    return _WS_RE.sub(" ", t).strip().lower()


def strip_html(text: str) -> str:
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text or ""))).strip()


def make_excerpt(text: str, max_chars: int = 240) -> str:
    """Short teaser for storage. Never the full article."""
    t = strip_html(text)
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"


def matches_any(url: str, patterns: tuple[str, ...] | list[str]) -> bool:
    low = url.lower()
    return any(p.lower() in low for p in patterns)
