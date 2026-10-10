"""Author leaning aggregates. Never a label on a person: a statistic about rated articles, with N."""

from __future__ import annotations

import sqlite3
from statistics import mean

from news_analyzer import db

CAVEAT = ("נתון זה מבוסס על דירוג אוטומטי של מודל בינה מלאכותית לכתבות בלבד, במדגם קטן. "
          "הוא אינו מעיד על עמדותיו האישיות של הכותב/ת, ועשוי לשקף את סוג הנושאים שעליהם הוא/היא כותב/ת.")


def lean_phrase(avg: float) -> str:
    if avg <= -1.0:
        return "שמאלה"
    if avg <= -0.4:
        return "מעט שמאלה"
    if avg < 0.4:
        return "למרכז, ללא נטייה ברורה"
    if avg < 1.0:
        return "מעט ימינה"
    return "ימינה"


def is_person(author: str | None, non_person: tuple[str, ...]) -> bool:
    if not author or len(author) < 4:
        return False
    low = author.lower()
    return not any(p.lower() in low for p in non_person)


def author_profile(conn: sqlite3.Connection, author: str | None, *, min_articles: int,
                   non_person: tuple[str, ...]) -> dict | None:
    """None if no (person) author. Otherwise {n, shown, text?, caveat?, avg?}; text only when n >= min."""
    if not is_person(author, non_person):
        return None
    scores = db.author_overall_scores(conn, author)
    n = len(scores)
    if n < min_articles:
        return {"author": author, "n": n, "shown": False, "min": min_articles}
    avg = mean(scores)
    return {
        "author": author, "n": n, "shown": True, "avg": round(avg, 2),
        "text": f"כתבות של כותב/ת זה נוטות {lean_phrase(avg)}, על סמך {n} כתבות שנותחו.",
        "caveat": CAVEAT,
    }
