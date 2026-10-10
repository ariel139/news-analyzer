import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from news_analyzer import db
from news_analyzer.analyzer.schema import parse_llm_output, to_db_row
from news_analyzer.collectors.models import ArticleCandidate
from news_analyzer.web import app as webapp

ANALYSIS = {
    "article_type": "opinion", "topic": "politics",
    "evidence_phrases": ["ממשלה הרסנית"],
    "explanation": "הכותב משתמש בביטוי ממשלה הרסנית ומציג רק צד אחד של הוויכוח.",
    "favored_side": "left",
    "security": {"applicable": False, "score": 0, "confidence": "high"},
    "religion_state": {"applicable": False, "score": 0, "confidence": "high"},
    "economy": {"applicable": False, "score": 0, "confidence": "high"},
    "tone": {"score": 3, "confidence": "high"},
    "overall": {"applicable": True, "score": -1, "confidence": "medium"},
    "summary": "טור דעה הקורא להחלפת הממשלה בטענה שמדיניותה פוגעת במוסדות המדינה ובאזרחים.",
}


@pytest.fixture
def seeded_db(tmp_path):
    path = tmp_path / "t.db"
    conn = db.connect(path)
    now = datetime.now(timezone.utc)
    items = [ArticleCandidate(outlet="ynet", url=f"https://ynet.example/{i}", title=f"כותרת מספר {i}",
                              published_at=now - timedelta(minutes=i), author="דנה כהן") for i in range(7)]
    items.append(ArticleCandidate(outlet="haaretz", url="https://haaretz.example/.premium/1", title="בתשלום",
                                  published_at=now, paywalled=True))
    db.insert_candidates(conn, items)
    result = parse_llm_output(json.dumps(ANALYSIS, ensure_ascii=False))
    for aid in range(1, 7):  # 6 analyzed articles by the same author
        db.save_text(conn, aid, "טקסט פנימי סודי שאסור להציג", None)
        db.save_analysis(conn, aid, to_db_row(result, evidence=["ממשלה הרסנית"], model="test",
                                              prompt_version="v1", duration_sec=1, created_at=db.iso(now)))
    conn.close()
    return path


@pytest.fixture
def client(seeded_db):
    def conn_override():
        c = db.connect(seeded_db)
        try:
            yield c
        finally:
            c.close()

    webapp.app.dependency_overrides[webapp.get_conn] = conn_override
    yield TestClient(webapp.app)
    webapp.app.dependency_overrides.clear()
