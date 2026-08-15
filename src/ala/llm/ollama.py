"""OllamaProvider — a real HTTP client for a local Ollama server (no external APIs).

Talks to Ollama's native ``/api/chat`` (+ ``/api/tags`` for health). Non-streaming
and streaming are supported. The HTTP transport is injectable so the request build
+ response parsing are unit-testable without a live server. Implements the
``LLMClient``/``LLMProvider`` interface, so it drops into ``LLMBackedGenerator``.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Iterator

from ala.llm.provider import LLMConfig, Message

log = logging.getLogger("ala.llm.ollama")


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str = "qwen3", *, base_url: str = "http://localhost:11434",
                 temperature: float = 0.2, timeout: float = 120.0, keep_alive: str = "5m",
                 num_ctx: int = 8192, post: Callable | None = None,
                 stream_post: Callable | None = None, health: Callable | None = None) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self._post = post or self._http_post          # (path, payload) -> dict
        self._stream_post = stream_post or self._http_stream
        self._health = health or self._http_health

    @classmethod
    def from_config(cls, cfg: LLMConfig, **overrides) -> "OllamaProvider":
        return cls(cfg.model, base_url=cfg.base_url, temperature=cfg.temperature,
                   timeout=cfg.timeout, keep_alive=cfg.keep_alive, num_ctx=cfg.num_ctx, **overrides)

    # -- interface ------------------------------------------------------- #
    def available(self) -> bool:
        try:
            return self._health()
        except Exception:                              # unreachable / no server
            return False

    def complete(self, prompt: str, **kw) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kw)

    def chat(self, messages: list[Message], **kw) -> str:
        data = self._post("/api/chat", self._payload(messages, stream=False, **kw))
        return (data.get("message", {}) or {}).get("content", "").strip()

    def stream(self, messages: list[Message], **kw) -> Iterator[str]:
        for line in self._stream_post("/api/chat", self._payload(messages, stream=True, **kw)):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = (obj.get("message", {}) or {}).get("content", "")
            if piece:
                yield piece
            if obj.get("done"):
                break

    def _payload(self, messages, *, stream: bool, temperature=None, **_kw) -> dict:
        return {"model": self.model, "messages": messages, "stream": stream,
                "keep_alive": self.keep_alive,
                "options": {"temperature": self.temperature if temperature is None else temperature,
                            "num_ctx": self.num_ctx}}

    # -- real transport (httpx) ------------------------------------------ #
    def _http_post(self, path: str, payload: dict) -> dict:
        import httpx
        r = httpx.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _http_stream(self, path: str, payload: dict) -> Iterator[str]:
        import httpx
        with httpx.stream("POST", f"{self.base_url}{path}", json=payload, timeout=self.timeout) as r:
            r.raise_for_status()
            yield from r.iter_lines()

    def _model_present(self, names: list[str]) -> bool:
        """True if the configured model is among the pulled models. A config model
        without an explicit ``:tag`` matches any tag (``qwen3`` ⇢ ``qwen3:latest``)."""
        want = (self.model or "").lower()
        for raw in names:
            n = (raw or "").lower()
            if n == want or (":" not in want and n.split(":")[0] == want):
                return True
        return False

    def _http_health(self) -> bool:
        # Server reachable AND the configured model is actually pulled — otherwise a
        # generation call would 404 on the missing model. Reporting "unavailable" here
        # lets the factory fall back to the grounded extractive generator (no hard fail).
        import httpx
        r = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
        if r.status_code != 200:
            return False
        try:
            models = r.json().get("models") or []
        except Exception:
            return False
        return self._model_present([m.get("name", "") for m in models])
