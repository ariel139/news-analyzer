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


def test_index_rails_day_heading_and_new_poll(client):
    r = client.get("/")
    assert 'class="topics"' in r.text and 'data-filter="topic" data-value="politics"' in r.text
    assert 'class="rail-end"' in r.text and "במספרים" in r.text
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


def test_end_rail_stats_and_active_topic(client):
    r = client.get("/?topic=politics")
    assert "נותחו לאחרונה" not in r.text
    assert 'title="שמאל־מרכז: 6"' in r.text  # leaning histogram: all 6 fixtures score -1
    assert 'id="stats-panel" class="stats-panel" hidden' in r.text  # behind the "נתונים" button
    assert 'data-action="stats" aria-expanded="false" aria-controls="stats-panel"' in r.text
    assert "דעה</span>" in r.text and "75% מהכתבות נותחו" in r.text  # 6 of 8 analyzed
    assert SECRET not in r.text
    assert 'class="topic-link active" data-filter="topic" data-value="politics"' in r.text


def test_several_outlets(client):
    r = client.get("/?outlet=ynet&outlet=haaretz")
    assert 'name="outlet" value="ynet" checked' in r.text and 'name="outlet" value="haaretz" checked' in r.text
    assert 'data-clear="outlet" data-value="ynet"' in r.text and 'data-clear="outlet" data-value="haaretz"' in r.text
    frag = client.get("/fragments/feed?outlet=ynet&outlet=haaretz").text
    assert "כותרת מספר 0" in frag and "בתשלום" in frag
    assert "בתשלום" not in client.get("/fragments/feed?outlet=ynet").text
    assert len(client.get("/api/articles?outlet=ynet&outlet=haaretz").json()["items"]) == 8
    assert client.get("/api/articles?" + "&".join(f"outlet=o{i}" for i in range(21))).status_code == 422


def test_how_it_works_is_an_icon(client):
    r = client.get("/")
    assert 'href="/methodology" aria-label="איך זה עובד"' in r.text
    assert ">איך זה עובד<" not in r.text


def test_cards_open_the_drawer(client):
    r = client.get("/")
    assert 'id="drawer"' in r.text and 'id="drawer-body"' in r.text
    assert '<div id="drawer-body" class="drawer-body" aria-live="polite"></div>\n</aside>' in r.text  # nesting intact
    assert 'href="/article/1" hx-get="/fragments/article/1" hx-target="#drawer-body"' in r.text
    frag = client.get("/fragments/article/1").text
    assert 'id="drawer-title"' in frag and "כותרת מספר 0" in frag and 'href="/article/1"' in frag
    assert SECRET not in frag


def test_active_filter_chips(client):
    r = client.get("/?topic=politics&outlet=ynet&q=כותרת")
    assert 'data-clear="topic"' in r.text and 'data-clear="outlet"' in r.text and 'data-clear="q"' in r.text
    assert 'hx-swap-oob' not in r.text  # chips are swapped out-of-band only by the fragment
    frag = client.get("/fragments/feed?leaning=-1").text
    assert 'id="active-chips" class="chips" hx-swap-oob="true"' in frag and 'data-clear="leaning"' in frag
    assert 'data-clear=' not in client.get("/fragments/feed").text
