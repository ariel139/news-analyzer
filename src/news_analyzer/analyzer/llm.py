"""Minimal Ollama chat client (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """Ollama is not reachable or the model is not installed - not the article's fault."""


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
