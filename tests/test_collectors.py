from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from news_analyzer.collectors.feeds import parse_feed
from news_analyzer.collectors.http import PoliteClient, RobotsDisallowed
from news_analyzer.collectors.listing import parse_listing
from news_analyzer.collectors.normalize import make_excerpt, normalize_url, title_key
from news_analyzer.collectors.pages import extract_page
from news_analyzer.config import Outlet, load_outlets

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
OUTLET = Outlet(id="example", name="דוגמה", feeds=("https://news.example.co.il/rss",), paywall=(".premium",))


def test_parse_feed_fields_and_filters():
    items = parse_feed((FIX / "rss_basic.xml").read_bytes(), OUTLET, now=NOW, max_age_hours=48)
    # old item dropped by age, empty title dropped
    assert [i.title for i in items] == ["הממשלה אישרה את התקציב בקריאה ראשונה", "טור דעה למנויים"]
    first = items[0]
    assert first.outlet == "example"
    assert first.url == "https://news.example.co.il/article/123"  # tracking params + fragment stripped
    assert first.author == "ישראלה ישראלי"
    assert first.published_at == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    assert first.tags == ["כלכלה", "תקציב"]
    assert "<" not in first.excerpt and '"אחרי ויכוח ארוך"' in first.excerpt
    assert first.paywalled is False
    assert items[1].paywalled is True  # .premium URL pattern
    assert items[1].published_at == datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)  # +0300 -> UTC


def test_parse_feed_premium_flag():
    outlet = Outlet(id="paper", name="עיתון")
    items = parse_feed((FIX / "rss_premium_flag.xml").read_bytes(), outlet, now=NOW, max_age_hours=48)
    assert {i.title: i.paywalled for i in items} == {"כתבה חינמית": False, "כתבה בתשלום": True}


def test_parse_feed_garbage_is_empty():
    assert parse_feed(b"<html>not a feed</html>", OUTLET, now=NOW) == []


@pytest.mark.parametrize("raw,expected", [
    ("http://Example.co.il/a/b/?utm_source=x&id=5#frag", "https://example.co.il/a/b?id=5"),
    ("https://www.globes.co.il/news/article.aspx?did=1001558851#utm_source=RSS",
     "https://www.globes.co.il/news/article.aspx?did=1001558851"),
    ("https://x.co.il/", "https://x.co.il/"),
])
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


def test_title_key_ignores_punctuation_and_spacing():
    assert title_key('נתניהו:  "לא נוותר"') == title_key("נתניהו לא נוותר")


def test_make_excerpt_is_short():
    long = "מילה " * 200
    ex = make_excerpt(long, max_chars=50)
    assert len(ex) <= 51 and ex.endswith("…")


def test_extract_page_main_text_and_author():
    page = extract_page((FIX / "article.html").read_text(encoding="utf-8"))
    assert "תקציב הביטחון יגדל" in page.text
    assert "כל הזכויות שמורות" not in page.text
    assert page.author == "ישראלה ישראלי"


def test_parse_listing():
    html = (FIX / "listing.html").read_text(encoding="utf-8")
    items = parse_listing(html, "https://site.example.co.il/news", r"/news/article/\d+", OUTLET)
    assert [i.url for i in items] == [
        "https://site.example.co.il/news/article/111",
        "https://site.example.co.il/news/article/222",
    ]
    assert items[1].title == "כותרת שנייה של כתבה עם תגיות פנימיות"


def _client(handler) -> PoliteClient:
    return PoliteClient("TestBot/1.0", min_delay=0, transport=httpx.MockTransport(handler))


def test_polite_client_respects_robots_wildcards():
    def handler(req: httpx.Request):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: *@opinion\nDisallow: /private/\n")
        return httpx.Response(200, text="ok")

    with _client(handler) as c:
        assert c.get("https://a.example/news/1").text == "ok"
        with pytest.raises(RobotsDisallowed):
            c.get("https://a.example/private/x")
        with pytest.raises(RobotsDisallowed):
            c.get("https://a.example/item/5@opinion")


@pytest.mark.parametrize("status,allowed", [(404, True), (403, False), (503, False)])
def test_polite_client_robots_status_handling(status, allowed):
    def handler(req: httpx.Request):
        if req.url.path == "/robots.txt":
            return httpx.Response(status)
        return httpx.Response(200, text="ok")

    with _client(handler) as c:
        assert c.allowed("https://b.example/page") is allowed


def test_outlets_config_loads():
    reg = load_outlets(Path(__file__).parents[1] / "config" / "outlets.yaml")
    ids = [o.id for o in reg.outlets]
    assert len(ids) == len(set(ids))
    assert {"ynet", "haaretz", "globes"} <= {o.id for o in reg.enabled}
    assert all(o.feeds or o.listing or not o.enabled for o in reg.outlets)
