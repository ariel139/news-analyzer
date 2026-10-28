"""Cheap pre-LLM filter: is an article worth CPU time, judged from its URL, RSS tags and title alone?

Skipping is terminal, so the rules aim for precision: a keep-keyword in the title or tags (Netanyahu,
elections, IDF...) overrides every skip rule, e.g. a sports story about a team banned over the war.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SkipRules:
    url_patterns: tuple[str, ...] = ()   # substrings of the URL (section paths)
    tags: tuple[str, ...] = ()           # exact RSS category tags
    title_phrases: tuple[str, ...] = ()  # substrings of the title
    keep_keywords: tuple[str, ...] = ()  # substrings of title or tags that veto a skip

    def should_skip(self, url: str, title: str = "", tags: Iterable[str] = ()) -> bool:
        tags = [t.strip().lower() for t in tags]
        title = title.lower()
        if any(k.lower() in title or any(k.lower() in t for t in tags) for k in self.keep_keywords):
            return False
        low_url = url.lower()
        return (any(p.lower() in low_url for p in self.url_patterns)
                or any(t.lower() in tags for t in self.tags)
                or any(p.lower() in title for p in self.title_phrases))
