from pathlib import Path

import pytest

from news_analyzer.config import load_outlets
from news_analyzer.triage import SkipRules

RULES = load_outlets(Path(__file__).parents[1] / "config" / "outlets.yaml").skip_rules


@pytest.mark.parametrize("url, title, tags", [
    ("https://www.israelhayom.co.il/sport/world-soccer/article/1", "שער בדקה ה-90", []),
    ("https://www.israelhayom.co.il/tech/apps/article/2", "השדרוג החדש של האפליקציה", ["אפליקציות"]),
    ("https://www.israelhayom.co.il/magazine/shishabat/article/3", "5 טעויות עיצוב בבית", ["שישבת", "מוספים"]),
    ("https://www.ynet.co.il/news/article/abc", "גשם ראשון בדרום", ["תחזית", "מזג אוויר"]),  # opaque URL
    ("https://www.israelhayom.co.il/news/x/article/4", "האמנה נחתמה | היום בהיסטוריה", []),
])
def test_non_political_is_skipped(url, title, tags):
    assert RULES.should_skip(url, title, tags)


@pytest.mark.parametrize("url, title, tags", [
    ("https://www.ynet.co.il/news/article/abc", "ממשלת נתניהו הבאה", ["בנימין נתניהו"]),
    ("https://www.israelhayom.co.il/magazine/hashavua/article/5", "קולות מפתיעים לפני הבחירות", ["ישראל השבוע"]),
    # a skip rule matches, but a keep-keyword wins
    ("https://www.haaretz.co.il/sport/world-soccer/1", "חרם על נבחרת ישראל", []),
    ("https://www.ynet.co.il/news/article/abc", "סופה בדרום", ["מזג אוויר", "צה\"ל"]),
])
def test_political_is_kept(url, title, tags):
    assert not RULES.should_skip(url, title, tags)


def test_tags_match_exactly_and_ignore_case():
    rules = SkipRules(tags=("ForReal",))
    assert rules.should_skip("https://x/1", "", [" forreal "])
    assert not rules.should_skip("https://x/1", "", ["ForReal Sport"])
