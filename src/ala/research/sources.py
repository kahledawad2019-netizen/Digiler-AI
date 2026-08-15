"""SourceQualityEvaluator — score, rank and de-duplicate web sources.

Deterministic heuristics (no network): domain **authority** (TLD + curated
educational/reference domains), **freshness** (published date), **educational
value** (title/snippet signals), **spam** signals, **duplicate** detection (domain
+ title/URL), and a combined **trust** score used to rank and gate sources.
Config-driven allow/deny lists — nothing user-facing is hardcoded beyond sensible
defaults.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ala.research.models import ResearchConfig, ScoredSource, SourceScore, WebResult

_EDU_DOMAINS = {
    "arxiv.org": 1.0, "wikipedia.org": 0.85, "docs.python.org": 0.95, "scholar.google.com": 0.9,
    "nature.com": 0.95, "acm.org": 0.95, "ieee.org": 0.95, "springer.com": 0.9,
    "sciencedirect.com": 0.9, "pytorch.org": 0.95, "tensorflow.org": 0.95, "scikit-learn.org": 0.95,
    "developer.mozilla.org": 0.9, "khanacademy.org": 0.85, "coursera.org": 0.8, "edx.org": 0.8,
    "towardsdatascience.com": 0.6, "medium.com": 0.5, "stackoverflow.com": 0.75, "github.com": 0.7,
}
_TLD_AUTHORITY = {"edu": 0.9, "gov": 0.9, "org": 0.7, "ac": 0.85}
_EDU_WORDS = re.compile(r"\b(tutorial|guide|introduction|lecture|course|documentation|"
                        r"explained|definition|concept|paper|study|reference|how to|example)\b", re.I)
_SPAM_WORDS = re.compile(r"\b(buy now|free download|click here|cheap|casino|porn|crypto giveaway|"
                         r"discount|coupon|earn money|viagra)\b", re.I)
_DATE = re.compile(r"(20\d{2})[-/](\d{1,2})(?:[-/](\d{1,2}))?")


class SourceQualityEvaluator:
    def __init__(self, config: ResearchConfig | None = None,
                 allow: dict | None = None, deny: set | None = None) -> None:
        self.config = config or ResearchConfig()
        self.allow = {**_EDU_DOMAINS, **(allow or {})}
        self.deny = deny or set()

    # -- scoring ---------------------------------------------------------- #
    def score(self, r: WebResult) -> SourceScore:
        dom = r.domain
        text = f"{r.title} {r.snippet}"
        authority = self._authority(dom)
        freshness = self._freshness(r.published or text)
        educational = min(1.0, 0.4 + 0.15 * len(_EDU_WORDS.findall(text)))
        spam = min(1.0, 0.25 * len(_SPAM_WORDS.findall(text)) + (0.5 if dom in self.deny else 0.0))
        domain_quality = 0.0 if dom in self.deny else authority
        citation_quality = 0.8 if dom in self.allow else (0.5 if authority >= 0.7 else 0.3)
        trust = max(0.0, min(1.0,
                    0.40 * authority + 0.15 * freshness + 0.20 * educational +
                    0.15 * citation_quality - 0.50 * spam))
        return SourceScore(authority=round(authority, 3), freshness=round(freshness, 3),
                           educational=round(educational, 3), domain_quality=round(domain_quality, 3),
                           citation_quality=round(citation_quality, 3), spam=round(spam, 3),
                           duplicate=False, trust=round(trust, 3))

    def _authority(self, domain: str) -> float:
        if domain in self.allow:
            return self.allow[domain]
        for known, val in self.allow.items():
            if domain.endswith("." + known) or domain == known:
                return val
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        parts = domain.split(".")
        if len(parts) >= 2 and parts[-2] in _TLD_AUTHORITY:
            return _TLD_AUTHORITY[parts[-2]]
        return _TLD_AUTHORITY.get(tld, 0.45)

    def _freshness(self, s: str) -> float:
        m = _DATE.search(s or "")
        if not m:
            return 0.5                                     # unknown → neutral
        year, month = int(m.group(1)), int(m.group(2) or 1)
        try:
            dt = datetime(year, month, 1, tzinfo=timezone.utc)
        except ValueError:
            return 0.5
        age_days = (datetime.now(timezone.utc) - dt).days
        return max(0.0, min(1.0, 1.0 - age_days / (5 * 365)))   # 0 at ~5 years old

    # -- rank + dedupe ---------------------------------------------------- #
    def evaluate(self, results: list[WebResult]) -> list[ScoredSource]:
        seen: set[str] = set()
        scored: list[ScoredSource] = []
        for r in results:
            s = self.score(r)
            key = self._dedupe_key(r)
            if key in seen:
                s.duplicate = True
            else:
                seen.add(key)
            scored.append(ScoredSource(r, s))
        # rank: non-duplicate, trust desc; duplicates sink to the bottom
        scored.sort(key=lambda ss: (not ss.score.duplicate, ss.score.trust), reverse=True)
        return scored

    @staticmethod
    def _dedupe_key(r: WebResult) -> str:
        base = re.sub(r"[#?].*$", "", r.url.rstrip("/")).lower()
        return base or (r.domain + "::" + r.title.lower().strip())

    def select(self, results: list[WebResult], k: int | None = None) -> list[ScoredSource]:
        k = k or self.config.top_sources
        ranked = self.evaluate(results)
        return [s for s in ranked
                if not s.score.duplicate and s.score.trust >= self.config.min_source_trust][:k]
