from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ArticleCandidate:
    """One article as discovered by a collector, before it is stored."""

    outlet: str
    url: str
    title: str
    published_at: datetime  # timezone-aware, UTC
    author: str | None = None
    excerpt: str = ""
    tags: list[str] = field(default_factory=list)
    paywalled: bool = False


@dataclass
class PageText:
    """Result of fetching and extracting an article page."""

    text: str
    author: str | None = None
