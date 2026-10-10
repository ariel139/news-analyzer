"""Polite HTTP: honours robots.txt (with wildcards, via protego) and per-host rate limits."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

import httpx
from protego import Protego

log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    pass


class PoliteClient:
    def __init__(self, user_agent: str, timeout: float = 20.0, min_delay: float = 2.0,
                 transport: httpx.BaseTransport | None = None):
        self.user_agent = user_agent
        self.min_delay = min_delay
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Language": "he,en;q=0.5"},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self._robots: dict[str, Protego | None] = {}  # None = disallow everything for this run
        self._last_hit: dict[str, float] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- robots -------------------------------------------------------------
    def _robots_for(self, url: str) -> Protego | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        return self._robots[origin]

    def _load_robots(self, origin: str) -> Protego | None:
        self._wait(origin)
        try:
            r = self._client.get(f"{origin}/robots.txt")
        except httpx.HTTPError as e:
            log.warning("robots.txt unreachable for %s (%s) - skipping host this run", origin, e)
            return None
        if r.status_code in (401, 403, 429) or r.status_code >= 500:
            # Blocked / bot-protected / overloaded: be conservative and stay away.
            log.warning("robots.txt for %s returned %s - treating host as disallowed", origin, r.status_code)
            return None
        if r.status_code >= 400:
            return Protego.parse("")  # no robots.txt = everything allowed
        return Protego.parse(r.text)

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(url)
        return rp is not None and rp.can_fetch(url, self.user_agent)

    # -- rate limit ---------------------------------------------------------
    def _delay_for(self, host: str) -> float:
        rp = self._robots.get(host)
        crawl_delay = rp.crawl_delay(self.user_agent) if rp else None
        return max(self.min_delay, float(crawl_delay or 0))

    def _wait(self, origin: str) -> None:
        last = self._last_hit.get(origin)
        if last is not None:
            remaining = self._delay_for(origin) - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_hit[origin] = time.monotonic()

    # -- public -------------------------------------------------------------
    def get(self, url: str) -> httpx.Response:
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        parts = urlsplit(url)
        self._wait(f"{parts.scheme}://{parts.netloc}")
        r = self._client.get(url)
        r.raise_for_status()
        return r
