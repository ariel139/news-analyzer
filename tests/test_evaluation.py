import json

import pytest

from news_analyzer import evaluation as ev


def test_qwk_perfect_and_chance():
    assert ev.quadratic_weighted_kappa([-2, -1, 0, 1, 2], [-2, -1, 0, 1, 2], -2, 2) == pytest.approx(1.0)
    assert ev.quadratic_weighted_kappa([-2, 2, -2, 2], [2, -2, 2, -2], -2, 2) < 0
    assert ev.quadratic_weighted_kappa([0], [0], -2, 2) is None
    assert ev.quadratic_weighted_kappa([0, 0], [0, 0], -2, 2) is None  # no variance -> undefined


@pytest.mark.parametrize("col,raw,expected", [
    ("overall", "-1", -1), ("overall", " 2 ", 2), ("overall", "3", None), ("overall", "NA", "na"),
    ("tone", "4", 4), ("tone", "-1", None), ("type", "Opinion", "opinion"), ("type", "blog", None),
    ("security", "", None),
])
def test_parse_label(col, raw, expected):
    assert ev._parse_label(col, raw) == expected


def _axis(score, applicable=True):
    return {"applicable": applicable, "score": score, "confidence": "high"}


def test_score_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "EVAL_DIR", tmp_path)
    monkeypatch.setattr(ev, "LABELS", tmp_path / "labels.csv")
    (tmp_path / "labels.csv").write_text(
        "id,outlet,title,url,type,security,religion,economy,tone,overall,notes\n"
        "1,a,t,u,opinion,2,na,na,3,2,\n"
        "2,a,t,u,news,0,na,-1,1,0,\n"
        "3,a,t,u,,,,,,,unlabeled row is ignored\n", encoding="utf-8-sig")
    preds = [
        {"id": 1, "ok": True, "result": {"article_type": "opinion", "security": _axis(1), "religion_state": _axis(0, False),
                                          "economy": _axis(0, False), "tone": {"score": 3, "confidence": "high"},
                                          "overall": _axis(2)}},
        {"id": 2, "ok": True, "result": {"article_type": "analysis", "security": _axis(0), "religion_state": _axis(1),
                                          "economy": _axis(-1), "tone": {"score": 1, "confidence": "high"},
                                          "overall": _axis(1)}},
    ]
    ev.predictions_path("m").write_text("\n".join(json.dumps(p) for p in preds), encoding="utf-8")
    r = ev.score("m")
    assert r["labeled"] == 2 and r["predicted_ok"] == 2
    assert r["type"]["accuracy"] == 50.0
    assert r["axes"]["overall"]["exact"] == 50.0 and r["axes"]["overall"]["within_1"] == 100.0
    assert r["axes"]["overall"]["bias"] == 0.5
    assert r["axes"]["security"]["mae"] == 0.5
    assert r["axes"]["religion"]["applicability_agreement"] == 50.0  # na/na agree, na/1 disagree
    ev.print_report(r)  # smoke
