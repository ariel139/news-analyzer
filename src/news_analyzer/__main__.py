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
    raise SystemExit("storing requires the database stage; use --dry-run")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="news_analyzer")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="fetch feeds once")
    c.add_argument("--dry-run", action="store_true", help="print what was found, don't store")
    c.set_defaults(func=cmd_collect)

    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
