"""Runtime settings (env vars prefixed NA_) and the outlet registry (config/outlets.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NA_", env_file=".env", extra="ignore")

    db_path: Path = Path("data/news.db")
    outlets_file: Path = Path("config/outlets.yaml")

    # Collection
    user_agent: str = "Mozilla/5.0 (compatible; NewsAnalyzerPOC/0.1; local research prototype)"
    request_timeout: float = 20.0
    per_domain_delay: float = 2.0  # seconds between requests to the same host (robots crawl-delay wins if larger)
    max_article_age_hours: int = 48  # ignore feed items older than this
    collect_interval_min: int = 15

    # LLM (Ollama)
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:8b"
    llm_num_ctx: int = 8192
    llm_temperature: float = 0.1
    llm_max_retries: int = 2  # extra attempts after the first one
    llm_timeout: float = 900.0
    llm_disable_thinking: bool = True  # Qwen3 "thinking" mode is slow on CPU and not needed here

    # Analysis budget - keep small on CPU-only machines
    analyze_max_per_run: int = 5
    analyze_time_budget_sec: int = 600
    analyze_max_age_hours: int = 24  # don't spend CPU on stale backlog
    max_analysis_chars: int = 3000  # article text is truncated to this before prompting
    min_analysis_chars: int = 400  # shorter extracted text = paywall/video/teaser, skipped

    # Retention & display
    text_retention_days: int = 30
    author_min_articles: int = 5
    timezone: str = "Asia/Jerusalem"


@dataclass(frozen=True)
class Outlet:
    id: str
    name: str
    feeds: tuple[str, ...] = ()
    listing: dict | None = None
    paywall: tuple[str, ...] = ()
    enabled: bool = True
    note: str = ""


@dataclass(frozen=True)
class OutletRegistry:
    outlets: tuple[Outlet, ...]
    skip_analysis_url_patterns: tuple[str, ...] = ()
    non_person_authors: tuple[str, ...] = field(default=())

    @property
    def enabled(self) -> list[Outlet]:
        return [o for o in self.outlets if o.enabled]

    def get(self, outlet_id: str) -> Outlet | None:
        return next((o for o in self.outlets if o.id == outlet_id), None)

    def name_of(self, outlet_id: str) -> str:
        o = self.get(outlet_id)
        return o.name if o else outlet_id


def load_outlets(path: Path) -> OutletRegistry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    outlets = tuple(
        Outlet(
            id=o["id"],
            name=o.get("name", o["id"]),
            feeds=tuple(o.get("feeds") or ()),
            listing=o.get("listing"),
            paywall=tuple(o.get("paywall") or ()),
            enabled=o.get("enabled", True),
            note=o.get("note", ""),
        )
        for o in raw.get("outlets", [])
    )
    return OutletRegistry(
        outlets=outlets,
        skip_analysis_url_patterns=tuple(raw.get("skip_analysis_url_patterns") or ()),
        non_person_authors=tuple(raw.get("non_person_authors") or ()),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_outlets() -> OutletRegistry:
    return load_outlets(get_settings().outlets_file)
