"""Scheduled worker: every N minutes collect (then analyze); purge old text daily."""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from news_analyzer import pipeline
from news_analyzer.config import get_outlets, get_settings

log = logging.getLogger(__name__)


def cycle() -> None:
    settings, registry = get_settings(), get_outlets()
    try:
        pipeline.run_collection(settings, registry)
    except Exception:
        log.exception("collection failed")
    try:
        pipeline.run_analysis(settings, registry)
    except Exception:
        log.exception("analysis failed")


def run_worker() -> None:
    settings = get_settings()
    sched = BlockingScheduler(timezone=settings.timezone)
    # max_instances=1 + coalesce: a slow cycle never overlaps the next one
    sched.add_job(cycle, "interval", minutes=settings.collect_interval_min, max_instances=1,
                  coalesce=True, next_run_time=_now(settings.timezone), id="cycle")
    sched.add_job(pipeline.run_purge, "cron", hour=4, args=[settings], id="purge")
    log.info("worker started: cycle every %d min", settings.collect_interval_min)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("worker stopped")


def _now(tz: str):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(tz))
