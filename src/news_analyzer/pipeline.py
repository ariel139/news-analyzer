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


MAX_FETCH_ATTEMPTS = 3


def make_analyzer(settings: Settings):
    from news_analyzer.analyzer.llm import OllamaClient
    from news_analyzer.analyzer.service import Analyzer

    client = OllamaClient(settings.ollama_url, settings.llm_model, timeout=settings.llm_timeout,
                          temperature=settings.llm_temperature, num_ctx=settings.llm_num_ctx,
                          disable_thinking=settings.llm_disable_thinking)
    return Analyzer(client, max_retries=settings.llm_max_retries, max_chars=settings.max_analysis_chars)


def run_analysis(settings: Settings, registry: OutletRegistry, *, limit: int | None = None,
                 time_budget_sec: int | None = None, article_ids: list[int] | None = None) -> dict:
    """Fetch text for the newest pending articles and rate them, within a count and time budget.

    Each article is rated once; the result is cached in `analyses`. Paywalled/skipped articles are
    never sent. If Ollama is down the run stops without marking articles as failed.
    """
    from news_analyzer.analyzer.llm import LLMUnavailable
    from news_analyzer.analyzer.schema import to_db_row
    from news_analyzer.analyzer.service import AnalysisFailed
    from news_analyzer.collectors.http import RobotsDisallowed
    from news_analyzer.collectors.pages import fetch_page_text

    limit = settings.analyze_max_per_run if limit is None else limit
    budget = settings.analyze_time_budget_sec if time_budget_sec is None else time_budget_sec
    counts = {"done": 0, "failed": 0, "skipped": 0}
    analyzer = make_analyzer(settings)
    try:
        analyzer.client.check()
    except LLMUnavailable as e:
        log.error("analysis skipped: %s", e)
        analyzer.client.close()
        return counts

    t0 = time.monotonic()
    with db.open_db(settings.db_path) as conn, \
            PoliteClient(settings.user_agent, settings.request_timeout, settings.per_domain_delay) as http:
        if article_ids:
            rows = conn.execute(
                f"SELECT * FROM articles WHERE id IN ({','.join('?' * len(article_ids))})", article_ids
            ).fetchall()
        else:
            # over-fetch: some candidates get skipped (robots/short text) without using LLM time
            rows = db.pending_articles(conn, limit * 4, settings.analyze_max_age_hours)

        for row in rows:
            if counts["done"] + counts["failed"] >= limit:
                break
            if time.monotonic() - t0 > budget:
                log.info("time budget of %ds used up; the rest waits for the next cycle", budget)
                break
            if row["status"] != "pending":  # cached (done) or never-analyze (paywalled/skipped)
                log.info("#%d is %s - not analyzing (use --reanalyze to redo)", row["id"], row["status"])
                continue
            aid, text, author = row["id"], row["analysis_text"], row["author"]

            if text is None:
                try:
                    page = fetch_page_text(http, row["url"])
                except RobotsDisallowed:
                    db.set_status(conn, aid, "skipped", "robots"); counts["skipped"] += 1
                    continue
                except Exception as e:
                    log.warning("[%s] fetch failed for %s: %s", row["outlet"], row["url"], e)
                    if db.bump_attempts(conn, aid) >= MAX_FETCH_ATTEMPTS:
                        db.set_status(conn, aid, "skipped", "fetch_error"); counts["skipped"] += 1
                    continue
                if len(page.text) < settings.min_analysis_chars:
                    # teaser/video page, or a paywall the feed didn't flag
                    db.set_status(conn, aid, "skipped", "short_text"); counts["skipped"] += 1
                    continue
                db.save_text(conn, aid, page.text, page.author)
                text, author = page.text, author or page.author

            def on_failure(attempt: int, error: str, raw: str, _aid=aid) -> None:
                db.log_failure(conn, _aid, analyzer.client.model, attempt, error, raw)

            log.info("[%s] analyzing #%d: %s", row["outlet"], aid, row["title"][:60])
            try:
                out = analyzer.analyze(row["title"], text, author=author, on_failure=on_failure)
            except LLMUnavailable as e:
                log.error("LLM unavailable, stopping this run: %s", e)
                break
            except AnalysisFailed as e:
                log.error("[%s] #%d %s", row["outlet"], aid, e)
                db.set_status(conn, aid, "failed", "invalid_output"); counts["failed"] += 1
                continue
            db.save_analysis(conn, aid, to_db_row(
                out.result, evidence=out.evidence, model=out.model, prompt_version=out.prompt_version,
                duration_sec=out.duration_sec, created_at=db.iso(db.utcnow())))
            counts["done"] += 1
            log.info("[%s] #%d done in %.0fs (%d attempt%s): type=%s overall=%s",
                     row["outlet"], aid, out.duration_sec, out.attempts, "" if out.attempts == 1 else "s",
                     out.result.article_type,
                     out.result.overall.score if out.result.overall.applicable else "n/a")
    analyzer.client.close()
    log.info("analysis: %s in %.0fs", counts, time.monotonic() - t0)
    return counts
