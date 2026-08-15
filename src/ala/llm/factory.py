"""LLM factory — select a provider by config, or a generator with graceful fallback.

``make_provider`` returns a configured provider (or ``None`` for ``provider: none``).
``available_provider`` returns it only if it is actually reachable (health check,
cached). ``make_generator`` returns an ``AnswerGenerator``: the LLM-backed one when a
provider is reachable, otherwise the offline ``ExtractiveGroundedGenerator`` — so
generation never hard-fails when Ollama is down (keeps CI/offline green).
"""

from __future__ import annotations

from ala.llm.ollama import OllamaProvider
from ala.llm.provider import LLMConfig, LLMProvider

_AVAIL_CACHE: dict[tuple, bool] = {}


def make_provider(settings=None, config: LLMConfig | None = None) -> LLMProvider | None:
    cfg = config or LLMConfig.from_settings(settings)
    p = cfg.provider.lower()
    if p == "ollama":
        return OllamaProvider.from_config(cfg)
    if p in ("openai", "openai-compatible") and cfg.base_url and cfg.model:
        from ala.rag.llm import OpenAICompatibleLLM
        return OpenAICompatibleLLM(cfg.base_url, cfg.model, cfg.api_key, cfg.temperature, cfg.timeout)
    return None


def available_provider(settings=None, config: LLMConfig | None = None) -> LLMProvider | None:
    cfg = config or LLMConfig.from_settings(settings)
    provider = make_provider(config=cfg)
    if provider is None:
        return None
    key = (cfg.provider, cfg.base_url, cfg.model)
    if key not in _AVAIL_CACHE:
        _AVAIL_CACHE[key] = bool(getattr(provider, "available", lambda: True)())
    return provider if _AVAIL_CACHE[key] else None


def make_generator(settings=None, config: LLMConfig | None = None):
    from ala.rag.llm import ExtractiveGroundedGenerator, LLMBackedGenerator
    provider = available_provider(settings, config)
    if provider is not None:
        return LLMBackedGenerator(provider, name=f"{provider.name}:{provider.model}")
    return ExtractiveGroundedGenerator()
