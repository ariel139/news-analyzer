"""Collect candidates from every enabled outlet."""

from __future__ import annotations

import logging

from news_analyzer.collectors.feeds import collect_feeds
from news_analyzer.collectors.http import PoliteClient
from news_analyzer.collectors.listing import collect_listing
from news_analyzer.collectors.models import ArticleCandidate
from news_analyzer.config import OutletRegistry, Settings

log = logging.getLogger(__name__)


def collect_all(client: PoliteClient, registry: OutletRegistry, settings: Settings) -> list[ArticleCandidate]:
    out: list[ArticleCandidate] = []
    for outlet in registry.enabled:
        if outlet.feeds:
            out.extend(collect_feeds(client, outlet, settings.max_article_age_hours))
        elif outlet.listing:
            out.extend(collect_listing(client, outlet))
        else:
            log.info("[%s] no feed or listing configured", outlet.id)
    return out
