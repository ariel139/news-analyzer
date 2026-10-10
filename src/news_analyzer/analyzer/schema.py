"""The JSON contract between us and the LLM, plus validation.

The same Pydantic model is (1) sent to Ollama as a JSON schema for constrained decoding and
(2) used to validate what comes back, so the two can never drift apart.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

TOPICS = ("security", "diplomacy", "politics", "economy", "law", "religion_state", "society",
          "health", "education", "culture", "sports", "other")
ARTICLE_TYPES = ("news", "analysis", "opinion")
CONFIDENCES = ("low", "medium", "high")
POLITICAL_AXES = ("security", "religion_state", "economy", "overall")
SIDES = ("left", "right", "none")

Confidence = Literal["low", "medium", "high"]

_HEB = re.compile(r"[֐-׿]")
_LAT = re.compile(r"[A-Za-z]")


def _require_hebrew(v: str) -> str:
    heb, lat = len(_HEB.findall(v)), len(_LAT.findall(v))
    if heb < 10 or heb < 0.7 * (heb + lat):
        raise ValueError("must be written in Hebrew")
    return v.strip()


class Axis(BaseModel):
    applicable: bool = Field(description="false if the article does not deal with this issue at all")
    score: Literal[-2, -1, 0, 1, 2]
    confidence: Confidence


class Tone(BaseModel):
    score: Literal[0, 1, 2, 3, 4]
    confidence: Confidence


class LLMAnalysis(BaseModel):
    """Field order matters: evidence and explanation come before the scores (reason, then rate).

    favored_side is committed to in words before any number: small models detected the slant but
    often put it on the wrong end of the scale, so overall must agree with it (see below).
    """

    model_config = ConfigDict(extra="ignore")

    article_type: Literal["news", "analysis", "opinion"]
    topic: Literal["security", "diplomacy", "politics", "economy", "law", "religion_state", "society",
                   "health", "education", "culture", "sports", "other"]
    evidence_phrases: list[str] = Field(min_length=1, max_length=4)
    explanation: str = Field(min_length=15, max_length=600)
    favored_side: Literal["left", "right", "none"] = Field(
        description="which side of the Israeli left-right spectrum the text's framing favors")
    security: Axis
    religion_state: Axis
    economy: Axis
    tone: Tone
    overall: Axis
    summary: str = Field(min_length=30, max_length=900)

    _hebrew_explanation = field_validator("explanation")(_require_hebrew)
    _hebrew_summary = field_validator("summary")(_require_hebrew)

    @model_validator(mode="after")
    def _overall_agrees_with_side(self) -> "LLMAnalysis":
        o = self.overall
        actual = "none" if not o.applicable or o.score == 0 else ("left" if o.score < 0 else "right")
        if actual != self.favored_side:
            need = {"left": "a negative overall score", "right": "a positive overall score",
                    "none": "overall score 0 or not applicable"}[self.favored_side]
            raise ValueError(f"favored_side is '{self.favored_side}', which requires {need}; "
                             f"got overall score {o.score} (applicable={o.applicable})")
        return self


class OutputError(ValueError):
    """The model output could not be turned into a valid LLMAnalysis."""


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_llm_output(raw: str) -> LLMAnalysis:
    text = _THINK.sub("", raw or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise OutputError("no JSON object found in output")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise OutputError(f"invalid JSON: {e}") from e
    try:
        return LLMAnalysis.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        raise OutputError(f"schema violation: {problems}") from e


def _inline_refs(schema: dict) -> dict:
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(dict(defs[node["$ref"].split("/")[-1]]))
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


def ollama_json_schema() -> dict:
    """Self-contained JSON schema (no $ref) for Ollama's `format` parameter."""
    return _inline_refs(LLMAnalysis.model_json_schema())


_QUOTES = re.compile(r"[\"'״׳“”‘’`]")
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", _QUOTES.sub("", s)).strip()


def verified_evidence(result: LLMAnalysis, source_text: str) -> list[str]:
    """Keep only evidence phrases that really occur in the text (models sometimes paraphrase)."""
    haystack = _norm(source_text)
    return [p.strip() for p in result.evidence_phrases if p.strip() and _norm(p) in haystack]


def to_db_row(result: LLMAnalysis, *, evidence: list[str], model: str, prompt_version: str,
              duration_sec: float, created_at: str) -> dict:
    def axis(a: Axis):
        return (a.score if a.applicable else None), a.confidence

    sec, sec_c = axis(result.security)
    rel, rel_c = axis(result.religion_state)
    eco, eco_c = axis(result.economy)
    ovr, ovr_c = axis(result.overall)
    return {
        "model": model, "prompt_version": prompt_version, "created_at": created_at,
        "duration_sec": round(duration_sec, 1),
        "article_type": result.article_type, "topic": result.topic,
        "favored_side": result.favored_side,
        "security_score": sec, "security_conf": sec_c,
        "religion_score": rel, "religion_conf": rel_c,
        "economy_score": eco, "economy_conf": eco_c,
        "tone_score": result.tone.score, "tone_conf": result.tone.confidence,
        "overall_score": ovr, "overall_conf": ovr_c,
        "explanation": result.explanation,
        "evidence": json.dumps(evidence, ensure_ascii=False),
        "summary": result.summary,
        "raw_json": result.model_dump_json(),
    }
