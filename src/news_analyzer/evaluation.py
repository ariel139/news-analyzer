"""Agreement between the model and hand labels on a small fixed set of articles.

    python -m news_analyzer eval-export        # pick ~30 articles, save text + empty labels.csv
    (fill eval/data/labels.csv by hand)
    python -m news_analyzer eval-run [--model qwen3:8b]   # predict (cached per model) + score
    python -m news_analyzer eval-score [--model ...]       # score existing predictions only

eval/data/ holds article text, so it is git-ignored.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path
from statistics import mean

from news_analyzer import db
from news_analyzer.collectors.http import PoliteClient
from news_analyzer.collectors.normalize import matches_any
from news_analyzer.collectors.pages import fetch_page_text
from news_analyzer.config import OutletRegistry, Settings

log = logging.getLogger(__name__)

EVAL_DIR = Path("eval/data")
ARTICLES = EVAL_DIR / "articles.jsonl"
LABELS = EVAL_DIR / "labels.csv"
LABEL_COLS = ["type", "security", "religion", "economy", "tone", "overall"]
AXES = {  # label column -> (prediction key in LLMAnalysis dump, min, max)
    "security": ("security", -2, 2), "religion": ("religion_state", -2, 2),
    "economy": ("economy", -2, 2), "tone": ("tone", 0, 4), "overall": ("overall", -2, 2),
}
_OPINION_URL = re.compile(r"opinion|/blogs?/|/column", re.IGNORECASE)


# --------------------------------------------------------------------------- export
def export(settings: Settings, registry: OutletRegistry, n: int = 30, overwrite: bool = False) -> int:
    if LABELS.exists() and not overwrite:
        raise SystemExit(f"{LABELS} exists - refusing to overwrite your labels (use --overwrite)")
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with db.open_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE status IN ('pending', 'done') ORDER BY published_at DESC"
        ).fetchall()
    rows = [r for r in rows if not matches_any(r["url"], registry.skip_analysis_url_patterns)]

    # Round-robin across outlets, opinion pieces first within each outlet, for variety.
    by_outlet: dict[str, list] = defaultdict(list)
    for r in sorted(rows, key=lambda r: not _OPINION_URL.search(r["url"])):
        by_outlet[r["outlet"]].append(r)
    ordered = [r for group in zip_longest(*by_outlet.values()) for r in group if r is not None]

    picked: list[dict] = []
    with PoliteClient(settings.user_agent, settings.request_timeout, settings.per_domain_delay) as http:
        for r in ordered:
            if len(picked) >= n:
                break
            text, author = r["analysis_text"], r["author"]
            if text is None:
                try:
                    page = fetch_page_text(http, r["url"])
                except Exception as e:
                    log.info("skip %s: %s", r["url"], e)
                    continue
                text, author = page.text, author or page.author
            if len(text) < settings.min_analysis_chars:
                continue
            picked.append({"id": r["id"], "outlet": r["outlet"], "url": r["url"], "title": r["title"],
                           "author": author, "text": text})
            log.info("picked %d/%d [%s] %s", len(picked), n, r["outlet"], r["title"][:60])

    with ARTICLES.open("w", encoding="utf-8") as f:
        for a in picked:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    with LABELS.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel shows Hebrew
        w = csv.writer(f)
        w.writerow(["id", "outlet", "title", "url", *LABEL_COLS, "notes"])
        for a in picked:
            w.writerow([a["id"], registry.name_of(a["outlet"]), a["title"], a["url"], *[""] * len(LABEL_COLS), ""])
    log.info("wrote %d articles to %s and %s", len(picked), ARTICLES, LABELS)
    return len(picked)


# --------------------------------------------------------------------------- labels / predictions
def _parse_label(col: str, raw: str):
    raw = (raw or "").strip().lower()
    if col == "type":
        return raw if raw in ("news", "analysis", "opinion") else None
    if raw in ("na", "n/a", "-"):
        return "na"
    try:
        v = int(raw)
    except ValueError:
        return None
    _, lo, hi = AXES[col]
    return v if lo <= v <= hi else None


def load_labels(path: Path | None = None) -> dict[int, dict]:
    out = {}
    with (path or LABELS).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            labels = {c: _parse_label(c, row.get(c, "")) for c in LABEL_COLS}
            if any(v is not None for v in labels.values()):
                out[int(row["id"])] = labels
    return out


def predictions_path(model: str) -> Path:
    return EVAL_DIR / f"predictions_{re.sub(r'[^A-Za-z0-9._-]', '_', model)}.jsonl"


def load_predictions(model: str) -> dict[int, dict]:
    p = predictions_path(model)
    if not p.exists():
        return {}
    preds = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        preds[rec["id"]] = rec
    return preds


def run(settings: Settings, model: str | None = None) -> None:
    """Predict every labeled article that has no prediction yet for this model (resumable)."""
    from news_analyzer.analyzer.service import AnalysisFailed
    from news_analyzer.pipeline import make_analyzer

    if model:
        settings = settings.model_copy(update={"llm_model": model})
    labels = load_labels()
    articles = {a["id"]: a for a in map(json.loads, ARTICLES.read_text(encoding="utf-8").splitlines())}
    done = load_predictions(settings.llm_model)
    todo = [i for i in labels if i in articles and i not in done]
    log.info("%d labeled, %d already predicted by %s, %d to go", len(labels), len(done), settings.llm_model,
             len(todo))
    analyzer = make_analyzer(settings)
    analyzer.client.check()
    with predictions_path(settings.llm_model).open("a", encoding="utf-8") as f:
        for k, aid in enumerate(todo, 1):
            a = articles[aid]
            try:
                out = analyzer.analyze(a["title"], a["text"], author=a.get("author"))
                rec = {"id": aid, "ok": True, "attempts": out.attempts, "sec": round(out.duration_sec, 1),
                       "result": out.result.model_dump()}
            except AnalysisFailed as e:
                rec = {"id": aid, "ok": False, "errors": e.errors}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            log.info("%d/%d #%d %s", k, len(todo), aid, "ok" if rec["ok"] else "FAILED")
    analyzer.client.close()


# --------------------------------------------------------------------------- metrics
def quadratic_weighted_kappa(a: list[int], b: list[int], lo: int, hi: int) -> float | None:
    """Cohen's kappa with quadratic weights - standard for ordinal ratings. None if undefined."""
    if len(a) < 2:
        return None
    k = hi - lo + 1
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x - lo][y - lo] += 1
    n = len(a)
    ha, hb = Counter(x - lo for x in a), Counter(y - lo for y in b)
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * obs[i][j]
            den += w * ha[i] * hb[j] / n
    return None if den == 0 else 1 - num / den


def _pred_value(result: dict, col: str):
    key, _, _ = AXES[col]
    v = result[key]
    if col != "tone" and not v["applicable"]:
        return "na"
    return v["score"]


def score(model: str) -> dict:
    labels, preds = load_labels(), load_predictions(model)
    pairs = [(labels[i], p["result"]) for i, p in preds.items() if i in labels and p.get("ok")]
    report: dict = {"model": model, "labeled": len(labels), "predicted_ok": len(pairs),
                    "failed": sum(1 for i, p in preds.items() if i in labels and not p.get("ok")), "axes": {}}

    t_pairs = [(lab["type"], res["article_type"]) for lab, res in pairs if lab["type"]]
    report["type"] = {"n": len(t_pairs),
                      "accuracy": _pct(sum(a == b for a, b in t_pairs), len(t_pairs)),
                      "confusion": dict(Counter(f"{a}->{b}" for a, b in t_pairs))}

    for col, (_, lo, hi) in AXES.items():
        both = [(lab[col], _pred_value(res, col)) for lab, res in pairs if lab[col] is not None]
        na_agree = sum((a == "na") == (b == "na") for a, b in both)
        num = [(a, b) for a, b in both if a != "na" and b != "na"]
        xs, ys = [a for a, _ in num], [b for _, b in num]
        report["axes"][col] = {
            "n_labeled": len(both),
            "applicability_agreement": _pct(na_agree, len(both)),
            "n_scored": len(num),
            "exact": _pct(sum(a == b for a, b in num), len(num)),
            "within_1": _pct(sum(abs(a - b) <= 1 for a, b in num), len(num)),
            "mae": round(mean(abs(a - b) for a, b in num), 2) if num else None,
            "bias": round(mean(b - a for a, b in num), 2) if num else None,  # >0: model rates higher
            "qwk": _round(quadratic_weighted_kappa(xs, ys, lo, hi)),
        }
    return report


def _pct(k: int, n: int) -> float | None:
    return round(100 * k / n, 1) if n else None


def _round(x: float | None) -> float | None:
    return None if x is None else round(x, 2)


def print_report(r: dict) -> None:
    print(f"\nModel: {r['model']}   labeled: {r['labeled']}   predicted: {r['predicted_ok']}   "
          f"failed: {r['failed']}")
    t = r["type"]
    print(f"Article type: n={t['n']} accuracy={t['accuracy']}%   {t['confusion']}")
    print(f"\n{'axis':10} {'n':>3} {'N/A agree%':>10} {'exact%':>7} {'±1%':>6} {'MAE':>5} {'bias':>6} {'QWK':>5}")
    for col, m in r["axes"].items():
        print(f"{col:10} {m['n_scored']:>3} {_fmt(m['applicability_agreement']):>10} {_fmt(m['exact']):>7} "
              f"{_fmt(m['within_1']):>6} {_fmt(m['mae']):>5} {_fmt(m['bias']):>6} {_fmt(m['qwk']):>5}")
    print("\nQWK: 1 = perfect, 0 = chance level; > 0.6 is usually considered substantial agreement.\n"
          "bias > 0 means the model rates higher (more right / hawkish / religious / free-market / loaded).")


def _fmt(v) -> str:
    return "-" if v is None else str(v)
