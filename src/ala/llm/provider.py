"""LLM provider interface + config (implements the Stage-12 ``LLMClient`` seam)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterator, Protocol, runtime_checkable

Message = dict            # {"role": "system"|"user"|"assistant", "content": str}


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    def available(self) -> bool: ...
    def complete(self, prompt: str, **kw) -> str: ...
    def chat(self, messages: list[Message], **kw) -> str: ...
    def stream(self, messages: list[Message], **kw) -> Iterator[str]: ...


@dataclass
class LLMConfig:
    provider: str = "ollama"                     # ollama | openai | none
    model: str = "qwen3"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 0.2
    timeout: float = 120.0
    keep_alive: str = "5m"
    num_ctx: int = 8192
    supported: list[str] = field(default_factory=lambda: [
        "qwen3", "qwen2.5", "llama3", "mistral", "gemma"])

    @classmethod
    def from_settings(cls, settings) -> "LLMConfig":
        c = (getattr(settings, "llm", None) or {}) if settings else {}
        return cls(
            provider=os.environ.get("ALA_LLM_PROVIDER", c.get("provider", "ollama")),
            model=os.environ.get("ALA_LLM_MODEL", c.get("model", "qwen3")),
            base_url=os.environ.get("ALA_LLM_BASE_URL", c.get("base_url", "http://localhost:11434")),
            api_key=os.environ.get("ALA_LLM_API_KEY", c.get("api_key", "")),
            temperature=float(c.get("temperature", 0.2)),
            timeout=float(c.get("timeout", 120.0)),
            keep_alive=str(c.get("keep_alive", "5m")),
            num_ctx=int(c.get("num_ctx", 8192)),
            supported=list(c.get("supported", ["qwen3", "qwen2.5", "llama3", "mistral", "gemma"])),
        )
