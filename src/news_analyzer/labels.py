"""Hebrew display labels. The DB and the LLM use the English keys."""

ARTICLE_TYPES = {"news": "ידיעה חדשותית", "analysis": "פרשנות", "opinion": "דעה"}

TOPICS = {
    "security": "ביטחון", "diplomacy": "מדיני", "politics": "פוליטיקה", "economy": "כלכלה",
    "law": "משפט", "religion_state": "דת ומדינה", "society": "חברה", "health": "בריאות",
    "education": "חינוך", "culture": "תרבות", "sports": "ספורט", "other": "אחר",
}

CONFIDENCE = {"low": "נמוכה", "medium": "בינונית", "high": "גבוהה"}

# key = DB column prefix; low/high = what the two ends of the scale mean
AXES = [
    {"key": "overall", "title": "סיכום שמאל–ימין", "low": "שמאל", "high": "ימין", "min": -2, "max": 2},
    {"key": "security", "title": "ביטחון ומדיניות חוץ", "low": "יוני", "high": "ניצי", "min": -2, "max": 2},
    {"key": "religion", "title": "דת ומדינה", "low": "ליברלי־חילוני", "high": "דתי־מסורתי",
     "min": -2, "max": 2},
    {"key": "economy", "title": "כלכלה", "low": "מעורבות מדינה", "high": "שוק חופשי", "min": -2, "max": 2},
    {"key": "tone", "title": "טון", "low": "ניטרלי", "high": "טעון רגשית", "min": 0, "max": 4},
]

LEANINGS = {"-2": "שמאל", "-1": "שמאל־מרכז", "0": "מרכז / ללא נטייה", "1": "ימין־מרכז", "2": "ימין",
            "na": "לא רלוונטי פוליטית"}

STATUS = {
    "pending": "ממתין לניתוח",
    "paywalled": "תוכן בתשלום – לא נותח",
    "failed": "הניתוח נכשל",
    "skipped": "לא נותח",
}

SKIP_REASONS = {
    "category": "קטגוריה שאינה מנותחת (ספורט, מזג אוויר, בידור)",
    "robots": "האתר אינו מתיר גישה אוטומטית לעמוד",
    "short_text": "אין מספיק טקסט זמין לניתוח (ייתכן תוכן בתשלום או וידאו)",
    "fetch_error": "לא ניתן היה לטעון את הכתבה",
    "invalid_output": "המודל לא החזיר תשובה תקינה",
}


def status_text(status: str, reason: str | None) -> str:
    base = STATUS.get(status, status)
    return f"{base}: {SKIP_REASONS[reason]}" if reason in SKIP_REASONS else base
