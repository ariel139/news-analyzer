"""Command line entry point: `python -m news_analyzer <command>`."""

from __future__ import annotations

import argparse
import logging
from collections import Counter

from news_analyzer.config import get_outlets, get_settings


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "trafilatura", "apscheduler.executors"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def cmd_collect(args) -> None:
    from news_analyzer.collectors.http import PoliteClient
    from news_analyzer.collectors.run import collect_all

    settings, registry = get_settings(), get_outlets()
    with PoliteClient(settings.user_agent, settings.request_timeout, settings.per_domain_delay) as client:
        items = collect_all(client, registry, settings)
    if args.dry_run:
        for i in sorted(items, key=lambda x: x.published_at, reverse=True):
            flag = " [paywall]" if i.paywalled else ""
            print(f"{i.published_at:%m-%d %H:%M}  {i.outlet:12} {i.title[:70]}{flag}")
        print("\nper outlet:", dict(Counter(i.outlet for i in items)))
        return
    from news_analyzer import pipeline

    pipeline.run_collection(settings, registry)


def cmd_stats(args) -> None:
    import json

    from news_analyzer import db

    with db.open_db(get_settings().db_path) as conn:
        print(json.dumps(db.stats(conn), ensure_ascii=False, indent=2))


def cmd_purge(args) -> None:
    from news_analyzer import pipeline

    pipeline.run_purge(get_settings())


def cmd_analyze(args) -> None:
    from news_analyzer import db, pipeline

    settings = get_settings()
    if args.reanalyze and args.id:
        with db.open_db(settings.db_path) as conn:
            conn.executemany("UPDATE articles SET status = 'pending' WHERE id = ? AND status != 'paywalled'",
                             [(i,) for i in args.id])
    pipeline.run_analysis(settings, get_outlets(), limit=args.limit, time_budget_sec=args.budget,
                          article_ids=args.id)


def cmd_llm_check(args) -> None:
    from news_analyzer.analyzer.llm import LLMUnavailable
    from news_analyzer.pipeline import make_analyzer

    settings = get_settings()
    client = make_analyzer(settings).client
    try:
        names = client.check()
    except LLMUnavailable as e:
        raise SystemExit(f"NOT OK: {e}")
    print(f"OK: Ollama at {settings.ollama_url}, model {settings.llm_model} installed. All models: {names}")


def cmd_worker(args) -> None:
    from news_analyzer.worker import run_worker

    run_worker()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="news_analyzer")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="fetch feeds once and store new articles")
    c.add_argument("--dry-run", action="store_true", help="print what was found, don't store")
    c.set_defaults(func=cmd_collect)

    a = sub.add_parser("analyze", help="rate pending articles once (newest first)")
    a.add_argument("--limit", type=int, default=None, help="max articles to send to the LLM")
    a.add_argument("--budget", type=int, default=None, help="time budget in seconds")
    a.add_argument("--id", type=int, action="append", help="analyze specific article id(s)")
    a.add_argument("--reanalyze", action="store_true", help="with --id: discard cached rating and redo")
    a.set_defaults(func=cmd_analyze)
    sub.add_parser("llm-check", help="verify Ollama is reachable and the model is pulled").set_defaults(
        func=cmd_llm_check)

    sub.add_parser("stats", help="article counts by status/outlet").set_defaults(func=cmd_stats)
    sub.add_parser("purge", help="delete stored article text past retention").set_defaults(func=cmd_purge)
    sub.add_parser("worker", help="run the scheduler (collect + analyze every N minutes)").set_defaults(
        func=cmd_worker)

    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
