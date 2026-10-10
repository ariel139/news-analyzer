SECRET = "טקסט פנימי סודי"


def test_feed_lists_newest_first_without_text(client):
    r = client.get("/api/articles")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 8
    assert SECRET not in r.text
    assert items[0]["published_at"] >= items[-1]["published_at"]


def test_filters(client):
    assert {i["outlet"] for i in client.get("/api/articles?outlet=haaretz").json()["items"]} == {"haaretz"}
    assert len(client.get("/api/articles?leaning=-1").json()["items"]) == 6
    assert len(client.get("/api/articles?leaning=2").json()["items"]) == 0
    assert len(client.get("/api/articles?type=opinion&topic=politics").json()["items"]) == 6
    assert client.get("/api/articles?leaning=7").status_code == 422


def test_article_detail_and_author_profile(client):
    d = client.get("/api/articles/1").json()
    assert SECRET not in str(d)
    assert d["analysis"]["article_type_he"] == "דעה"
    assert d["analysis"]["favored_side"] == "left" and d["analysis"]["favored_side_he"] == "שמאל"
    overall = next(a for a in d["analysis"]["axes"] if a["key"] == "overall")
    assert overall["score"] == -1 and overall["confidence_he"] == "בינונית"
    prof = d["author_profile"]
    assert prof["shown"] and prof["n"] == 6 and "על סמך 6 כתבות" in prof["text"]


def test_paywalled_article_has_no_analysis(client):
    d = client.get("/api/articles/8").json()
    assert d["analysis"] is None and d["status"] == "paywalled" and d["author_profile"] is None


def test_author_profile_hidden_below_threshold(client, seeded_db):
    from news_analyzer import db
    from news_analyzer.authors import author_profile

    conn = db.connect(seeded_db)
    p = author_profile(conn, "דנה כהן", min_articles=10, non_person=())
    assert p == {"author": "דנה כהן", "n": 6, "shown": False, "min": 10}
    assert author_profile(conn, "מערכת ynet", min_articles=1, non_person=("ynet",)) is None


def test_404(client):
    assert client.get("/api/articles/999").status_code == 404
