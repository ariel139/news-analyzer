"""Rate one article: prompt -> LLM -> validate -> retry with the error on malformed output."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from news_analyzer.analyzer.prompt import PROMPT_VERSION, build_messages, repair_message
from news_analyzer.analyzer.schema import LLMAnalysis, OutputError, ollama_json_schema, parse_llm_output, \
    verified_evidence

log = logging.getLogger(__name__)


class ChatClient(Protocol):
    model: str

    def chat(self, messages: list[dict], json_schema: dict | None = None) -> str: ...


@dataclass
class Outcome:
    result: LLMAnalysis
    evidence: list[str]
    attempts: int
    duration_sec: float
    model: str
    prompt_version: str = PROMPT_VERSION


@dataclass
class AnalysisFailed(Exception):
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"analysis failed after {len(self.errors)} attempts: {self.errors[-1] if self.errors else ''}"


FailureHook = Callable[[int, str, str], None]  # (attempt, error, raw_output)


class Analyzer:
    def __init__(self, client: ChatClient, *, max_retries: int = 2, max_chars: int = 3000):
        self.client = client
        self.max_retries = max_retries
        self.max_chars = max_chars
        self._schema = ollama_json_schema()

    def analyze(self, title: str, body: str, *, author: str | None = None,
                on_failure: FailureHook | None = None) -> Outcome:
        messages = build_messages(title, body, author=author, max_chars=self.max_chars)
        errors: list[str] = []
        t0 = time.monotonic()
        for attempt in range(1, self.max_retries + 2):
            raw = self.client.chat(messages, self._schema)  # LLMUnavailable propagates
            try:
                result = parse_llm_output(raw)
            except OutputError as e:
                errors.append(str(e))
                log.warning("attempt %d: invalid output: %s", attempt, e)
                if on_failure:
                    on_failure(attempt, str(e), raw)
                messages = [*messages, {"role": "assistant", "content": raw}, repair_message(str(e))]
                continue
            evidence = verified_evidence(result, f"{title}\n{body}")
            if not evidence:
                log.info("no evidence phrase matched the text verbatim (model paraphrased)")
            return Outcome(result, evidence, attempt, time.monotonic() - t0, self.client.model)
        raise AnalysisFailed(errors)
