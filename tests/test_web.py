SECRET = "טקסט פנימי סודי"


def test_index_renders_rtl_feed(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'dir="rtl"' in r.text and "כותרת מספר 0" in r.text
    assert SECRET not in r.text
    assert 'hx-get="/fragments/article/1"' in r.text


def test_feed_fragment_filters(client):
    r = client.get("/fragments/feed?outlet=haaretz")
    assert "בתשלום" in r.text and "כותרת מספר" not in r.text


def test_analyzed_only_filter(client):
    r = client.get("/fragments/feed?analyzed=1")
    assert "כותרת מספר 0" in r.text
    assert "כותרת מספר 6" not in r.text and "בתשלום" not in r.text  # pending and paywalled hidden
    assert 'name="analyzed" value="1" role="switch" checked' in client.get("/?analyzed=1").text


def test_outlet_logo_on_card(client):
    r = client.get("/")
    assert 'src="/static/logos/ynet.png"' in r.text
    assert client.get("/static/logos/ynet.png").status_code == 200


def test_panel_shows_analysis_link_and_author_profile(client):
    r = client.get("/fragments/article/1")
    assert r.status_code == 200
    assert SECRET not in r.text
    assert "למה הדירוג הזה" in r.text and "ממשלה הרסנית" in r.text
    assert "על סמך 6 כתבות" in r.text
    assert 'href="https://ynet.example/0"' in r.text and 'rel="noopener noreferrer"' in r.text
    assert "לא רלוונטי לכתבה זו" in r.text  # security axis N/A


def test_panel_for_paywalled(client):
    assert "תוכן בתשלום" in client.get("/fragments/article/8").text


def test_methodology(client):
    r = client.get("/methodology")
    assert r.status_code == 200 and "מגבלות חשובות" in r.text


def test_headline_search(client):
    r = client.get("/fragments/feed?q=מספר 3")
    assert "כותרת מספר 3" in r.text and "כותרת מספר 4" not in r.text
    assert "לא נמצאו כתבות" in client.get("/fragments/feed?q=100%").text  # % is literal, not a wildcard
    assert len(client.get("/api/articles?q=כותרת").json()["items"]) == 7


def test_index_sidebar_day_heading_and_new_poll(client):
    r = client.get("/")
    assert "נושאים השבוע" in r.text and 'data-filter="topic" data-value="politics"' in r.text
    assert '<h2>היום</h2>' in r.text
    assert 'hx-get="/fragments/new?since=' in r.text


def test_load_more_skips_repeated_day_heading(client):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    day = datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat()
    assert "<h2>היום</h2>" not in client.get(f"/fragments/feed?after_day={day}").text
    assert client.get("/fragments/feed?after_day=bad").status_code == 422


def test_new_articles_fragment(client):
    assert "כתבות חדשות" in client.get("/fragments/new?since=2000-01-01T00:00:00%2B00:00").text
    assert client.get("/fragments/new?since=2999-01-01T00:00:00%2B00:00").text.strip() == ""
    assert client.get("/fragments/new?since=nope").status_code == 422


def test_article_page(client):
    r = client.get("/article/1")
    assert r.status_code == 200
    assert SECRET not in r.text
    assert "<h1>כותרת מספר 0</h1>" in r.text and "למה הדירוג הזה" in r.text
    assert 'data-copy="/article/1"' in r.text
    assert client.get("/article/999").status_code == 404
