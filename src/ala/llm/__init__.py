"""LLM provider abstraction (production).

A single ``LLMProvider`` interface with a real **Ollama** backend (local, no
external APIs) and an OpenAI-compatible backend, selected by config with zero code
changes. Providers implement the existing Stage-12 ``LLMClient`` protocol
(``complete``), so they plug straight into ``LLMBackedGenerator`` and every
capability (GraphRAG, agents, function-calling) uses them for free. If the
configured provider is unreachable, ``make_generator`` falls back to the offline
extractive-grounded generator — nothing ever hard-fails.
"""

from ala.llm.factory import available_provider, make_generator, make_provider
from ala.llm.ollama import OllamaProvider
from ala.llm.provider import LLMProvider, Message

__all__ = ["LLMProvider", "Message", "OllamaProvider", "make_provider",
           "make_generator", "available_provider"]
