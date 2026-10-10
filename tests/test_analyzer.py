import copy
import json

import httpx
import pytest

from news_analyzer.analyzer.llm import LLMUnavailable, OllamaClient
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


def test_evidence_must_occur_in_text_ignoring_quote_marks():
    r = parse_llm_output(json.dumps(VALID, ensure_ascii=False))
    assert verified_evidence(r, TITLE + "\n" + BODY) == ["מפקירה את מעמד הביניים"]


def test_db_row_maps_not_applicable_to_null():
    r = parse_llm_output(json.dumps(VALID, ensure_ascii=False))
    row = to_db_row(r, evidence=[], model="m", prompt_version="v1", duration_sec=1.23, created_at="t")
    assert row["security_score"] is None and row["economy_score"] == -1 and row["overall_score"] == 0
    assert row["tone_score"] == 1 and row["duration_sec"] == 1.2


def test_ollama_schema_is_self_contained():
    s = json.dumps(ollama_json_schema())
    assert "$ref" not in s and "$defs" not in s
    assert "evidence_phrases" in s


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
