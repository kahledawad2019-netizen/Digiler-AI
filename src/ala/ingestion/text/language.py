"""Language detection with confidence.

The platform only needs to distinguish its supported languages (English/Arabic
today), and script is a near-perfect signal for that pair. So the default
detector is a dependency-free **script-based** detector: it counts Arabic vs
Latin letters and returns a language + a confidence in [0, 1].

It is hidden behind the ``LanguageDetector`` protocol, so a statistical model
(fastText / lingua) can be swapped in later without touching the pipeline
(Dependency Inversion).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class LanguageResult:
    language: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)


@runtime_checkable
class LanguageDetector(Protocol):
    def detect(self, text: str) -> LanguageResult: ...


def _count_scripts(text: str) -> tuple[int, int]:
    arabic = latin = 0
    for ch in text:
        code = ord(ch)
        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F or 0x08A0 <= code <= 0x08FF:
            arabic += 1
        elif ("a" <= ch.lower() <= "z"):
            latin += 1
    return arabic, latin


class ScriptLanguageDetector:
    """Arabic vs English by script proportion. Fast, deterministic, no deps."""

    def __init__(self, default: str = "en") -> None:
        self.default = default

    def detect(self, text: str) -> LanguageResult:
        arabic, latin = _count_scripts(text or "")
        total = arabic + latin
        if total == 0:
            return LanguageResult(self.default, 0.0, {"ar": 0.0, "en": 0.0})
        ar_score = arabic / total
        en_score = latin / total
        if ar_score >= en_score:
            return LanguageResult("ar", round(ar_score, 4), {"ar": round(ar_score, 4), "en": round(en_score, 4)})
        return LanguageResult("en", round(en_score, 4), {"ar": round(ar_score, 4), "en": round(en_score, 4)})
