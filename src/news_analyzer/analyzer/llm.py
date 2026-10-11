"""Chat clients: Ollama (default, local) and an optional OpenAI-compatible hosted API (OpenRouter)."""

from __future__ import annotations

import logging
import time
from typing import Callable

import httpx

log = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """The LLM backend is not reachable, refuses us or lacks the model - not the article's fault."""


class OllamaClient:
    def __init__(self, base_url: str, model: str, *, timeout: float = 900, temperature: float = 0.1,
                 num_ctx: int = 8192, disable_thinking: bool = True,
                 transport: httpx.BaseTransport | None = None):
        self.model = model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self._send_think = disable_thinking
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def check(self) -> list[str]:
        """Return installed model names; raise LLMUnavailable if the server or model is missing."""
        try:
            r = self._http.get("/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"cannot reach Ollama at {self._http.base_url}: {e}") from e
        names = [m["name"] for m in r.json().get("models", [])]
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        if wanted not in names:
            raise LLMUnavailable(f"model {self.model!r} is not pulled. Run: ollama pull {self.model}")
        return names

    def chat(self, messages: list[dict], json_schema: dict | None = None) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx, "seed": 42},
        }
        if json_schema is not None:
            body["format"] = json_schema
        if self._send_think:
            body["think"] = False
        try:
            r = self._http.post("/api/chat", json=body)
            if r.status_code == 400 and "think" in r.text.lower() and self._send_think:
                log.info("model %s does not support the think flag; retrying without it", self.model)
                self._send_think = False
                body.pop("think")
                r = self._http.post("/api/chat", json=body)
            if r.status_code == 404:
                raise LLMUnavailable(f"model {self.model!r} not found on Ollama server: {r.text[:200]}")
            r.raise_for_status()
        except httpx.TimeoutException as e:
            raise LLMUnavailable(f"Ollama timed out: {e}") from e
        except httpx.TransportError as e:
            raise LLMUnavailable(f"cannot reach Ollama: {e}") from e
        return r.json()["message"]["content"]


class OpenAICompatClient:
    """Hosted chat-completions API (OpenRouter by default). Article text leaves this machine, so the request
    forbids providers that retain or train on prompts and requires them to honour the JSON schema.

    The API key lives only in the Authorization header: it is not in repr() and no message below includes it.
    """

    RETRY_STATUS = (429, 500, 502, 503, 504)

    def __init__(self, api_url: str, api_key: str, model: str, *, label: str | None = None, timeout: float = 120,
                 temperature: float = 0.1, max_retries: int = 2, providers: tuple[str, ...] = (),
                 transport: httpx.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.api_model = model
        self.timeout = timeout
        self.label = label or ("openrouter" if "openrouter.ai" in api_url else "openai")
        self.model = f"{self.label}:{model}"  # what analyses.model records, so hosted ratings are recognisable
        self.temperature = temperature
        self.max_retries = max_retries
        self.providers = providers
        self.total_cost_usd = 0.0
        self.total_tokens = (0, 0)  # prompt, completion
        self._prices: tuple[float, float] | None = None  # $/token (prompt, completion), for when usage has no cost
        self._sleep = sleep
        self._clock = clock
        self._url = api_url.rstrip("/")
        self._http = httpx.Client(base_url=self._url, timeout=timeout, transport=transport,
                                  headers={"Authorization": f"Bearer {api_key}"})

    def __repr__(self) -> str:
        return f"OpenAICompatClient(url={self._url!r}, model={self.api_model!r})"

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        """One call with at most `max_retries` retries on 429/5xx; every failure becomes LLMUnavailable."""
        for attempt in range(self.max_retries + 1):
            try:
                r = self._send(method, path, **kw)
            except httpx.TimeoutException as e:
                raise LLMUnavailable(f"hosted LLM timed out ({type(e).__name__})") from None
            except httpx.TransportError as e:
                raise LLMUnavailable(f"cannot reach hosted LLM at {self._url} ({type(e).__name__})") from None
            if r.status_code in self.RETRY_STATUS and attempt < self.max_retries:
                try:
                    wait = float(r.headers.get("Retry-After", ""))
                except ValueError:
                    wait = 2.0 * 2 ** attempt
                log.warning("hosted LLM answered %d; retrying in %.0fs", r.status_code, min(wait, 60))
                self._sleep(min(wait, 60))
                continue
            if r.status_code >= 400:
                raise LLMUnavailable(self._explain(r))
            return r
        raise AssertionError("unreachable")

    def _send(self, method: str, path: str, **kw) -> httpx.Response:
        """httpx's timeout is per read; OpenRouter sends keep-alive whitespace while an upstream provider works,
        so a hung provider would never time out. Enforce a deadline on the whole response instead."""
        t0, body = self._clock(), bytearray()
        with self._http.stream(method, path, **kw) as r:
            for chunk in r.iter_bytes():
                body += chunk
                if self._clock() - t0 > self.timeout:
                    raise httpx.ReadTimeout(f"no complete answer within {self.timeout:.0f}s", request=r.request)
        # iter_bytes() already decompressed the body, so the encoding/length headers no longer apply
        headers = [(k, v) for k, v in r.headers.items() if k.lower() not in ("content-encoding", "content-length")]
        return httpx.Response(r.status_code, headers=headers, content=bytes(body), request=r.request)

    def _explain(self, r: httpx.Response) -> str:
        hint = {401: "API key rejected (check NA_LLM_API_KEY)", 402: "out of credit or over the key's spending limit",
                403: "forbidden (key, region or moderation)", 404: f"model or endpoint not found ({self.api_model!r})",
                429: "rate limited", 400: "request rejected (model/provider may not support the JSON schema or "
                                          "reasoning settings)"}.get(r.status_code, "server error")
        try:
            err = r.json()["error"]
            detail = str(err.get("message", ""))[:160] if isinstance(err, dict) else ""
        except (ValueError, KeyError, TypeError):
            detail = ""
        return f"hosted LLM HTTP {r.status_code}: {hint}" + (f" - {detail}" if detail else "")

    def check(self) -> list[str]:
        """Verify the key (OpenRouter /key) and that the model exists; return the model ids offered."""
        if self.label == "openrouter":
            self._request("GET", "/key")
        try:
            data = self._request("GET", "/models").json()["data"]
        except (ValueError, KeyError, TypeError):
            raise LLMUnavailable("unexpected answer from GET /models") from None
        ids = [m["id"] for m in data]
        mine = next((m for m in data if m["id"] == self.api_model), None)
        if mine is None:
            raise LLMUnavailable(f"model {self.api_model!r} is not offered by {self._url}")
        try:
            pr = mine["pricing"]
            self._prices = (float(pr["prompt"]), float(pr["completion"]))
        except (KeyError, TypeError, ValueError):
            self._prices = None
        return ids

    def chat(self, messages: list[dict], json_schema: dict | None = None) -> str:
        body = {
            "model": self.api_model,
            "messages": messages,
            "temperature": self.temperature,
            "seed": 42,
            # a normal answer is ~300-450 tokens; the cap turns a runaway generation (repeating or endless
            # whitespace inside the JSON) into truncated output, which the normal retry path handles
            "max_tokens": 2000,
            "reasoning": {"enabled": False},
            "usage": {"include": True},
            # no logging/training on prompts, and only providers that really support the schema
            "provider": {"data_collection": "deny", "require_parameters": True},
        }
        if self.providers:
            body["provider"].update(order=list(self.providers), allow_fallbacks=False)
        if json_schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "analysis", "strict": True, "schema": json_schema}}
        data = self._request("POST", "/chat/completions", json=body).json()
        self._record_usage(data.get("usage") or {}, data.get("provider"))
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ""  # parsed as invalid output -> normal retry path

    def _record_usage(self, usage: dict, provider: str | None = None) -> None:
        pt, ct = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        cost = usage.get("cost")
        if cost is None and self._prices:
            cost = pt * self._prices[0] + ct * self._prices[1]
        cost = float(cost or 0.0)
        self.total_cost_usd += cost
        self.total_tokens = (self.total_tokens[0] + pt, self.total_tokens[1] + ct)
        log.info("usage via %s: %d prompt + %d completion tokens, $%.5f (run total $%.5f)", provider or "?", pt, ct,
                 cost, self.total_cost_usd)
