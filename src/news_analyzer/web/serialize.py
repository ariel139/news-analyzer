"""Row -> dict for the API and templates. Only whitelisted fields; article text never included."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from news_analyzer import labels
from news_analyzer.config import OutletRegistry


def _local(iso_ts: str, tz: str) -> datetime:
    return datetime.fromisoformat(iso_ts).astimezone(ZoneInfo(tz))


def analysis_dict(row: sqlite3.Row) -> dict | None:
    if row["article_type"] is None:
        return None
    axes = []
    for ax in labels.AXES:
        score = row[f"{ax['key']}_score"]
        axes.append({**ax, "score": score, "applicable": score is not None,
                     "confidence": row[f"{ax['key']}_conf"],
                     "confidence_he": labels.CONFIDENCE.get(row[f"{ax['key']}_conf"], "")})
    return {
        "article_type": row["article_type"],
        "article_type_he": labels.ARTICLE_TYPES.get(row["article_type"], row["article_type"]),
        "topic": row["topic"],
        "topic_he": labels.TOPICS.get(row["topic"], row["topic"]),
        "axes": axes,
        "explanation": row["explanation"],
        "evidence": json.loads(row["evidence"] or "[]"),
        "summary": row["summary"],
        "model": row["model"],
        "analyzed_at": row["analyzed_at"],
    }


def article_dict(row: sqlite3.Row, registry: OutletRegistry, tz: str) -> dict:
    return {
        "id": row["id"],
        "outlet": row["outlet"],
        "outlet_name": registry.name_of(row["outlet"]),
        "title": row["title"],
        "url": row["url"],
        "author": row["author"],
        "published_at": row["published_at"],
        "published_local": _local(row["published_at"], tz),
        "status": row["status"],
        "status_he": labels.status_text(row["status"], row["skip_reason"]),
        "analysis": analysis_dict(row),
    }
