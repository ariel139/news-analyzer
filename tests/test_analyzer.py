import copy
import json

import httpx
import pytest

from news_analyzer.analyzer.llm import LLMUnavailable, OllamaClient, OpenAICompatClient
from news_analyzer.analyzer.prompt import build_messages, strip_author, truncate
from news_analyzer.analyzer.schema import OutputError, ollama_json_schema, parse_llm_output, to_db_row, \
    verified_evidence
from news_analyzer.analyzer.service import AnalysisFailed, Analyzer

TITLE = "הממשלה אישרה את התקציב בקריאה ראשונה"
BODY = ("שרי הממשלה הצביעו הערב בעד הצעת התקציב. גורמים באופוזיציה טענו כי היא \"מפקירה את מעמד הביניים\". "
        "במשרד האוצר הגיבו כי מדובר ב\"תקציב אחראי\".")

VALID = {
    "article_type": "news",
    "topic": "economy",
    "evidence_phrases": ["מפקירה את מעמד הביניים", "ביטוי שלא מופיע בכתבה"],
    "explanation": "הכתבה מביאה את עמדת האופוזיציה ואת תגובת האוצר באופן מאוזן יחסית.",
    "favored_side": "none",
    "security": {"applicable": False, "score": 0, "confidence": "high"},
    "religion_state": {"applicable": False, "score": 0, "confidence": "high"},
    "economy": {"applicable": True, "score": -1, "confidence": "medium"},
    "tone": {"score": 1, "confidence": "high"},
    "overall": {"applicable": True, "score": 0, "confidence": "low"},
    "summary": "הממשלה אישרה את הצעת התקציב בקריאה ראשונה. האופוזיציה מתחה ביקורת, והאוצר הגן על ההצעה.",
}


def variant(**changes):
    d = copy.deepcopy(VALID)
    d.update(changes)
    return json.dumps(d, ensure_ascii=False)


# ------------------------------------------------------------------ parsing / validation
def test_valid_output_parses():
    r = parse_llm_output(json.dumps(VALID, ensure_ascii=False))
    assert r.article_type == "news" and r.economy.score == -1


def test_think_block_and_code_fence_are_tolerated():
    raw = "<think>hmm</think>\n```json\n" + json.dumps(VALID, ensure_ascii=False) + "\n```"
    assert parse_llm_output(raw).topic == "economy"


@pytest.mark.parametrize("raw,fragment", [
    ("", "no JSON object"),
    ("I think the article is left leaning.", "no JSON object"),
    ('{"article_type": "news", ', "no JSON object"),
    ('{"article_type": "news",}', "invalid JSON"),
    (variant(article_type="editorial"), "article_type"),
    (variant(topic="weather"), "topic"),
    (variant(overall={"applicable": True, "score": 5, "confidence": "high"}), "overall.score"),
    (variant(tone={"score": -1, "confidence": "high"}), "tone.score"),
    (variant(economy={"applicable": True, "score": 1, "confidence": "very high"}), "economy.confidence"),
    (variant(evidence_phrases=[]), "evidence_phrases"),
    (variant(explanation="The article is balanced and fair to both sides of the debate."), "explanation"),
    (variant(summary="קצר"), "summary"),
    (variant(favored_side="center"), "favored_side"),
    # other scripts slipped into the Hebrew text
    (variant(explanation="הכתבה מציגה את הדחייה של الانتخابات באופן מאוזן יחסית."), "explanation"),
    (variant(summary="הממשלה אישרה את התקציב, והכתבה מביאה 報導 של שני הצדדים באופן מאוזן."), "summary"),
    # the grammar pattern: an ASCII double quote would end the JSON string during constrained decoding
    (variant(explanation='הכתבה מביאה את עמדת צה"ל ואת תגובת האוצר באופן מאוזן.'), "explanation"),
])
def test_invalid_outputs_rejected(raw, fragment):
    with pytest.raises(OutputError) as e:
        parse_llm_output(raw)
    assert fragment in str(e.value)


def test_missing_field_rejected():
    d = copy.deepcopy(VALID)
    del d["overall"]
    with pytest.raises(OutputError, match="overall"):
        parse_llm_output(json.dumps(d, ensure_ascii=False))


@pytest.mark.parametrize("side,overall", [
    ("left", {"applicable": True, "score": -1, "confidence": "medium"}),
    ("right", {"applicable": True, "score": 2, "confidence": "high"}),
    ("none", {"applicable": False, "score": 0, "confidence": "low"}),
])
def test_consistent_side_and_overall_accepted(side, overall):
    r = parse_llm_output(variant(favored_side=side, overall=overall))
    assert r.favored_side == side and r.overall.score == overall["score"]


@pytest.mark.parametrize("side,overall,expected", [
    ("right", {"applicable": True, "score": 0, "confidence": "high"}, (True, 1)),
    ("left", {"applicable": False, "score": 0, "confidence": "medium"}, (True, -1)),
    ("left", {"applicable": True, "score": 2, "confidence": "high"}, (True, -2)),
    ("none", {"applicable": True, "score": -2, "confidence": "high"}, (True, 0)),
])
def test_overall_follows_favored_side_instead_of_retrying(side, overall, expected):
    r = parse_llm_output(variant(favored_side=side, overall=overall))
    assert (r.overall.applicable, r.overall.score) == expected and r.overall.confidence == "low"


def test_foreign_script_rejected_even_without_the_pattern():
    """Backends that ignore the schema pattern still get caught by the validator."""
    from news_analyzer.analyzer.schema import _require_hebrew
    with pytest.raises(ValueError, match="Hebrew only"):
        _require_hebrew("הכתבה מביאה את עמדת האופוזיציה 報導 באופן מאוזן יחסית.")


def test_hebrew_gershayim_and_latin_names_allowed():
    r = parse_llm_output(variant(explanation="לפי בלומברג ו-AI, צה״ל והאוצר הגיבו (באופן מאוזן) – 5% בלבד."))
    assert "צה״ל" in r.explanation


def test_evidence_must_occur_in_text_ignoring_quote_marks():
    r = parse_llm_output(json.dumps(VALID, ensure_ascii=False))
    assert verified_evidence(r, TITLE + "\n" + BODY) == ["מפקירה את מעמד הביניים"]


def test_db_row_maps_not_applicable_to_null():
    r = parse_llm_output(json.dumps(VALID, ensure_ascii=False))
    row = to_db_row(r, evidence=[], model="m", prompt_version="v1", duration_sec=1.23, created_at="t")
    assert row["security_score"] is None and row["economy_score"] == -1 and row["overall_score"] == 0
    assert row["tone_score"] == 1 and row["duration_sec"] == 1.2 and row["favored_side"] == "none"


def test_ollama_schema_is_self_contained():
    s = json.dumps(ollama_json_schema())
    assert "$ref" not in s and "$defs" not in s
    assert "evidence_phrases" in s
    props = ollama_json_schema()["properties"]
    assert props["explanation"]["pattern"].startswith("^[") and "pattern" in props["summary"]
    assert "pattern" not in props["evidence_phrases"]["items"]  # copied verbatim, may contain any quote mark


# ------------------------------------------------------------------ prompt
def test_author_name_removed_from_prompt():
    msgs = build_messages(TITLE, "מאת ישראלה ישראלי. " + BODY, author="ישראלה ישראלי", max_chars=3000)
    assert "ישראלה ישראלי" not in msgs[1]["content"]
    assert strip_author("abc", None) == "abc"


def test_truncate_marks_cut():
    t = truncate("משפט ראשון. " * 50, 100)
    assert len(t) < 140 and t.endswith("[...הטקסט קוצר...]")


# ------------------------------------------------------------------ retry loop
class FakeClient:
    model = "fake"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls: list[list[dict]] = []

    def chat(self, messages, json_schema=None):
        self.calls.append(messages)
        return self.outputs.pop(0)


def test_retry_after_malformed_output_then_success():
    client = FakeClient(["not json", json.dumps(VALID, ensure_ascii=False)])
    failures = []
    out = Analyzer(client, max_retries=2).analyze(TITLE, BODY, on_failure=lambda *a: failures.append(a))
    assert out.attempts == 2 and out.result.topic == "economy"
    assert len(failures) == 1 and failures[0][0] == 1 and failures[0][2] == "not json"
    # the error was fed back to the model on the second call
    assert "invalid" in client.calls[1][-1]["content"]


def test_gives_up_after_max_retries():
    client = FakeClient(["bad"] * 3)
    with pytest.raises(AnalysisFailed) as e:
        Analyzer(client, max_retries=2).analyze(TITLE, BODY)
    assert len(e.value.errors) == 3 and len(client.calls) == 3


# ------------------------------------------------------------------ Ollama client
def _ollama(handler):
    return OllamaClient("http://ollama", "qwen3:8b", transport=httpx.MockTransport(handler))


def test_ollama_chat_sends_schema_and_no_thinking():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "{}"}})

    assert _ollama(handler).chat([{"role": "user", "content": "x"}], {"type": "object"}) == "{}"
    assert seen["format"] == {"type": "object"} and seen["think"] is False and seen["stream"] is False


def test_ollama_check_reports_missing_model():
    c = _ollama(lambda req: httpx.Response(200, json={"models": [{"name": "llama3:latest"}]}))
    with pytest.raises(LLMUnavailable, match="ollama pull qwen3:8b"):
        c.check()


def test_ollama_unreachable():
    def handler(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMUnavailable):
        _ollama(handler).chat([{"role": "user", "content": "x"}])


# ------------------------------------------------------------------ hosted (OpenAI-compatible) backend
KEY = "sk-or-v1-SECRETKEY123"


def _completion(content: str | None = None, cost: float | None = 0.0003) -> dict:
    usage = {"prompt_tokens": 2400, "completion_tokens": 450}
    if cost is not None:
        usage["cost"] = cost
    return {"choices": [{"message": {"content": content or json.dumps(VALID, ensure_ascii=False)}}], "usage": usage}


def hosted(handler, **kw) -> OpenAICompatClient:
    kw.setdefault("sleep", lambda s: None)
    return OpenAICompatClient("https://openrouter.ai/api/v1", KEY, "google/gemma-4-26b-a4b-it",
                              transport=httpx.MockTransport(handler), **kw)


def test_hosted_request_body_and_headers():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion())

    c = hosted(handler)
    schema = ollama_json_schema()
    assert json.loads(c.chat([{"role": "user", "content": "x"}], schema))["topic"] == "economy"
    b = seen["body"]
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    assert b["model"] == "google/gemma-4-26b-a4b-it"  # the API gets the bare id ...
    assert c.model == "openrouter:google/gemma-4-26b-a4b-it"  # ... the DB records the prefixed one
    assert b["response_format"] == {"type": "json_schema",
                                    "json_schema": {"name": "analysis", "strict": True, "schema": schema}}
    assert b["provider"] == {"data_collection": "deny", "require_parameters": True}
    assert b["reasoning"] == {"enabled": False} and b["temperature"] == 0.1 and b["max_tokens"] == 2000
    assert c.total_cost_usd == pytest.approx(0.0003) and c.total_tokens == (2400, 450)


def test_hosted_pinned_providers_without_fallback():
    seen = {}
    c = hosted(lambda r: seen.update(body=json.loads(r.content)) or httpx.Response(200, json=_completion()),
               providers=("deepinfra",))
    c.chat([{"role": "user", "content": "x"}])
    assert seen["body"]["provider"] == {"data_collection": "deny", "require_parameters": True,
                                        "order": ["deepinfra"], "allow_fallbacks": False}


def test_hosted_key_never_in_repr_or_errors():
    c = hosted(lambda r: httpx.Response(401, json={"error": {"message": "bad key"}}))
    assert KEY not in repr(c) and KEY not in str(vars(c).get("_url"))
    with pytest.raises(LLMUnavailable) as e:
        c.chat([{"role": "user", "content": "SECRET ARTICLE TEXT"}])
    assert KEY not in str(e.value) and "SECRET ARTICLE TEXT" not in str(e.value)

    def boom(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LLMUnavailable) as e:
        hosted(boom).chat([{"role": "user", "content": "x"}])
    assert KEY not in str(e.value) and KEY not in repr(e.value.__cause__)


@pytest.mark.parametrize("status", [401, 402, 403, 404])
def test_hosted_client_errors_become_unavailable(status):
    calls = []
    c = hosted(lambda r: calls.append(1) or httpx.Response(status, json={}))
    with pytest.raises(LLMUnavailable, match=str(status)):
        c.chat([{"role": "user", "content": "x"}])
    assert len(calls) == 1  # not retried


def test_hosted_429_retried_with_retry_after_then_succeeds():
    answers = [httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(503), httpx.Response(200, json=_completion())]
    waits = []
    c = hosted(lambda r: answers.pop(0), sleep=waits.append)
    assert c.chat([{"role": "user", "content": "x"}])
    assert waits == [3.0, 4.0]  # Retry-After honoured, then exponential backoff


def test_hosted_total_deadline_despite_keepalive_whitespace():
    """OpenRouter keeps a slow request alive with whitespace, so httpx's per-read timeout never fires."""
    ticks = iter(range(0, 10_000, 50))

    def handler(request):
        return httpx.Response(200, content=iter([b" "] * 10 + [json.dumps(_completion()).encode()]))

    c = hosted(handler, clock=lambda: next(ticks))
    with pytest.raises(LLMUnavailable, match="timed out"):
        c.chat([{"role": "user", "content": "x"}])


def test_hosted_gzip_response_decoded_once():
    import gzip

    payload = gzip.compress(json.dumps(_completion()).encode())
    c = hosted(lambda r: httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=payload))
    assert json.loads(c.chat([{"role": "user", "content": "x"}]))["topic"] == "economy"


def test_hosted_gives_up_after_two_retries():
    calls = []
    c = hosted(lambda r: calls.append(1) or httpx.Response(429))
    with pytest.raises(LLMUnavailable, match="429"):
        c.chat([{"role": "user", "content": "x"}])
    assert len(calls) == 3


def test_hosted_cost_falls_back_to_listed_prices():
    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "google/gemma-4-26b-a4b-it",
                                                       "pricing": {"prompt": "0.000000068", "completion": "0.000000225"}}]})
        if request.url.path.endswith("/key"):
            return httpx.Response(200, json={"data": {}})
        return httpx.Response(200, json=_completion(cost=None))

    c = hosted(handler)
    c.check()
    c.chat([{"role": "user", "content": "x"}])
    assert c.total_cost_usd == pytest.approx(2400 * 0.068e-6 + 450 * 0.225e-6)


def test_hosted_check_reports_missing_model():
    c = hosted(lambda r: httpx.Response(200, json={"data": [{"id": "other/model"}]}))
    with pytest.raises(LLMUnavailable, match="not offered"):
        c.check()


def test_make_analyzer_defaults_to_ollama():
    from news_analyzer.config import Settings
    from news_analyzer.pipeline import make_analyzer

    s = Settings(_env_file=None)
    assert s.llm_provider == "ollama" and s.llm_api_key is None
    assert isinstance(make_analyzer(s).client, OllamaClient)


def test_make_analyzer_hosted_needs_key_and_hides_it():
    from news_analyzer.config import Settings
    from news_analyzer.pipeline import make_analyzer

    with pytest.raises(LLMUnavailable, match="NA_LLM_API_KEY"):
        make_analyzer(Settings(_env_file=None, llm_provider="openai"))
    s = Settings(_env_file=None, llm_provider="openai", llm_api_key=KEY, llm_model="google/gemma-4-26b-a4b-it")
    assert KEY not in repr(s) and KEY not in str(s)
    assert make_analyzer(s).client.model == "openrouter:google/gemma-4-26b-a4b-it"


def test_cost_cap_stops_a_run(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from news_analyzer import db, pipeline
    from news_analyzer.collectors.models import ArticleCandidate
    from news_analyzer.config import OutletRegistry, Settings

    path = tmp_path / "t.db"
    now = datetime.now(timezone.utc)
    with db.open_db(path) as conn:
        db.insert_candidates(conn, [ArticleCandidate(outlet="ynet", url=f"https://ynet.example/{i}", title=f"{TITLE} {i}",
                                                     published_at=now - timedelta(minutes=i)) for i in range(4)])
        for i in range(1, 5):
            db.save_text(conn, i, BODY * 5, None)

    def handler(request):
        if request.url.path.endswith(("/key", "/models")):
            return httpx.Response(200, json={"data": [{"id": "google/gemma-4-26b-a4b-it"}]})
        return httpx.Response(200, json=_completion(cost=0.04))

    monkeypatch.setattr(pipeline, "make_analyzer", lambda s: Analyzer(hosted(handler)))
    settings = Settings(_env_file=None, db_path=path, llm_provider="openai", llm_api_key=KEY,
                        llm_max_cost_usd_per_run=0.05)
    counts = pipeline.run_analysis(settings, OutletRegistry(outlets=()), limit=4)
    assert counts["done"] == 2  # $0.04 < cap -> second article starts -> $0.08 >= cap -> stop
    with db.open_db(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM articles WHERE status='pending'").fetchone()[0] == 2
        assert conn.execute("SELECT DISTINCT model FROM analyses").fetchone()[0] == "openrouter:google/gemma-4-26b-a4b-it"
