"""LLM provider tests — Ollama request/response/streaming + factory fallback.

No live server: the HTTP transport is injected so we verify the exact request body
and response parsing. The graceful-fallback path (provider unreachable → extractive
generator) is what keeps CI/offline green.
"""

from __future__ import annotations

from ala.config.settings import load_settings
from ala.llm.factory import make_generator, make_provider
from ala.llm.ollama import OllamaProvider
from ala.llm.provider import LLMConfig
from ala.rag.llm import ExtractiveGroundedGenerator, LLMBackedGenerator


def _provider(*, reply="Hello from Qwen3.", capture=None, healthy=True) -> OllamaProvider:
    def post(path, payload):
        if capture is not None:
            capture.update({"path": path, "payload": payload})
        return {"message": {"role": "assistant", "content": reply}, "done": True}

    def stream(path, payload):
        for word in reply.split():
            import json
            yield json.dumps({"message": {"content": word + " "}, "done": False})
        import json
        yield json.dumps({"message": {"content": ""}, "done": True})

    return OllamaProvider("qwen3", post=post, stream_post=stream, health=lambda: healthy)


# -- request building + parsing --------------------------------------------- #
def test_ollama_chat_builds_request_and_parses():
    cap: dict = {}
    p = _provider(reply="A CNN uses convolution.", capture=cap)
    out = p.complete("what is a cnn")
    assert out == "A CNN uses convolution."
    assert cap["path"] == "/api/chat"
    body = cap["payload"]
    assert body["model"] == "qwen3" and body["stream"] is False
    assert body["messages"] == [{"role": "user", "content": "what is a cnn"}]
    assert body["options"]["temperature"] == 0.2 and body["options"]["num_ctx"] == 8192


def test_ollama_chat_with_system_message():
    cap: dict = {}
    p = _provider(capture=cap)
    p.chat([{"role": "system", "content": "be concise"}, {"role": "user", "content": "hi"}])
    assert cap["payload"]["messages"][0]["role"] == "system"


def test_ollama_streaming():
    p = _provider(reply="one two three")
    chunks = list(p.stream([{"role": "user", "content": "count"}]))
    assert "".join(chunks).split() == ["one", "two", "three"]


def test_available_reflects_health():
    assert _provider(healthy=True).available() is True
    assert _provider(healthy=False).available() is False


# -- factory + config ------------------------------------------------------- #
def test_config_from_settings_defaults_to_qwen3():
    cfg = LLMConfig.from_settings(load_settings(None))
    assert cfg.provider == "ollama" and cfg.model == "qwen3"
    assert cfg.base_url.endswith(":11434")


def test_make_provider_selects_backend():
    assert make_provider(config=LLMConfig(provider="ollama")).name == "ollama"
    assert make_provider(config=LLMConfig(provider="none")) is None
    oai = make_provider(config=LLMConfig(provider="openai", base_url="http://x", model="m"))
    assert oai is not None and oai.model == "m"


def test_make_generator_falls_back_when_unreachable():
    # provider 'none' → no LLM → extractive-grounded generator (offline default)
    gen = make_generator(config=LLMConfig(provider="none"))
    assert isinstance(gen, ExtractiveGroundedGenerator)


def test_llm_backed_generator_uses_provider():
    p = _provider(reply="grounded answer [C1].")
    gen = LLMBackedGenerator(p, name="ollama:qwen3")
    from ala.rag.models import ReasoningContext
    assert gen.answer(ReasoningContext(question="q"), "PROMPT") == "grounded answer [C1]."
