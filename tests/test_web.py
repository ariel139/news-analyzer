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
