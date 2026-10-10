"""Orchestration: collect -> store -> (analyze). Used by the CLI and the scheduled worker."""

from __future__ import annotations

import logging
import time

from news_analyzer import db
from news_analyzer.collectors.http import PoliteClient
from news_analyzer.collectors.run import collect_all
from news_analyzer.config import OutletRegistry, Settings

log = logging.getLogger(__name__)


def run_collection(settings: Settings, registry: OutletRegistry) -> int:
    t0 = time.monotonic()
    with PoliteClient(settings.user_agent, settings.request_timeout, settings.per_domain_delay) as client:
        items = collect_all(client, registry, settings)
    with db.open_db(settings.db_path) as conn:
        inserted = db.insert_candidates(conn, items, registry.skip_analysis_url_patterns)
    log.info("collection: %d items seen, %d new, %.1fs", len(items), inserted, time.monotonic() - t0)
    return inserted


def run_purge(settings: Settings) -> int:
    with db.open_db(settings.db_path) as conn:
        n = db.purge_old_text(conn, settings.text_retention_days)
    log.info("purge: cleared stored text of %d articles older than %d days", n, settings.text_retention_days)
    return n
