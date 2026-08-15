"""Web-search provider abstraction (config-selected, never hardcoded).

Real adapters: ``wikipedia`` (MediaWiki API, no key — the reliable default for an
educational assistant, auto-selects the ar/en Wikipedia by query script),
``duckduckgo`` (HTML endpoint, no key — often challenge-blocked for bots),
``tavily`` (API key — best broad-web results for production), ``google`` (Custom
Search JSON API, key + cx). ``local`` searches a local folder (offline research over
a cached corpus). ``disabled`` returns nothing so the pipeline degrades gracefully
with no network. All network calls use stdlib ``urllib`` (+ the already-present
BeautifulSoup for HTML) — no new dependency — and fail soft (return ``[]``) so a
provider outage never crashes an answer.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from ala.research.models import ResearchConfig, WebResult

log = logging.getLogger("ala.research.search")
_UA = "Mozilla/5.0 (compatible; DigilerAI-Research/1.0)"


@runtime_checkable
class WebSearchProvider(Protocol):
    name: str
    def search(self, query: str, k: int = 6) -> list[WebResult]: ...


class DisabledProvider:
    name = "disabled"
    def search(self, query: str, k: int = 6) -> list[WebResult]:
        return []


class LocalCacheProvider:
    """Offline provider: rank local .txt/.md/.html files by query-term overlap."""

    name = "local"

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def search(self, query: str, k: int = 6) -> list[WebResult]:
        if not self.folder.is_dir():
            return []
        terms = {w for w in query.lower().split() if len(w) > 2}
        scored: list[tuple[int, WebResult]] = []
        for f in sorted(self.folder.rglob("*")):
            if f.suffix.lower() not in (".txt", ".md", ".html", ".htm"):
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            overlap = sum(text.lower().count(t) for t in terms)
            if overlap:
                scored.append((overlap, WebResult(
                    title=f.stem.replace("-", " ").title(), url=f.as_uri(),
                    snippet=text.strip()[:200], provider=self.name,
                    raw={"path": str(f)})))
        scored.sort(key=lambda kv: kv[0], reverse=True)
        return [r for _, r in scored[:k]]


class WikipediaProvider:
    """Reliable, no-key web search via the MediaWiki API. Auto-selects the Arabic
    or English Wikipedia based on the query script (bilingual support)."""

    name = "wikipedia"

    def __init__(self, lang: str = "auto") -> None:
        self.lang = lang

    def _lang_for(self, query: str) -> str:
        if self.lang != "auto":
            return self.lang
        # any Arabic-script character → Arabic Wikipedia, else English
        return "ar" if any("؀" <= ch <= "ۿ" for ch in query) else "en"

    def search(self, query: str, k: int = 6) -> list[WebResult]:
        import re
        import urllib.parse
        import urllib.request
        lang = self._lang_for(query)
        params = urllib.parse.urlencode({"action": "query", "list": "search",
                                         "srsearch": query, "format": "json", "srlimit": k})
        url = f"https://{lang}.wikipedia.org/w/api.php?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:                              # network / parse failure
            log.warning("Wikipedia search failed: %s", exc)
            return []
        out: list[WebResult] = []
        for it in data.get("query", {}).get("search", [])[:k]:
            title = it.get("title", "")
            snippet = re.sub("<[^>]+>", "", it.get("snippet", "")).replace("&quot;", '"').strip()
            page = urllib.parse.quote(title.replace(" ", "_"))
            out.append(WebResult(title=title, url=f"https://{lang}.wikipedia.org/wiki/{page}",
                                 snippet=snippet, provider=self.name,
                                 raw={"pageid": it.get("pageid"), "lang": lang}))
        return out


class DuckDuckGoProvider:
    name = "duckduckgo"

    def search(self, query: str, k: int = 6) -> list[WebResult]:
        import urllib.parse
        import urllib.request
        from bs4 import BeautifulSoup
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                soup = BeautifulSoup(resp.read(), "html.parser")
        except Exception as exc:                              # network / parse failure
            log.warning("DuckDuckGo search failed: %s", exc)
            return []
        out: list[WebResult] = []
        for res in soup.select(".result")[:k]:
            a = res.select_one(".result__a")
            if not a:
                continue
            sn = res.select_one(".result__snippet")
            out.append(WebResult(title=a.get_text(" ", strip=True), url=a.get("href", ""),
                                 snippet=sn.get_text(" ", strip=True) if sn else "",
                                 provider=self.name))
        return out


class TavilyProvider:
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, k: int = 6) -> list[WebResult]:
        import urllib.request
        body = json.dumps({"api_key": self.api_key, "query": query,
                           "max_results": k}).encode("utf-8")
        try:
            req = urllib.request.Request("https://api.tavily.com/search", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning("Tavily search failed: %s", exc)
            return []
        return [WebResult(title=r.get("title", ""), url=r.get("url", ""),
                          snippet=r.get("content", ""), published=r.get("published_date"),
                          provider=self.name) for r in data.get("results", [])[:k]]


class GoogleProvider:
    name = "google"

    def __init__(self, api_key: str, cx: str) -> None:
        self.api_key = api_key
        self.cx = cx

    def search(self, query: str, k: int = 6) -> list[WebResult]:
        import urllib.parse
        import urllib.request
        params = urllib.parse.urlencode({"key": self.api_key, "cx": self.cx, "q": query, "num": k})
        try:
            with urllib.request.urlopen(
                    f"https://www.googleapis.com/customsearch/v1?{params}", timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning("Google search failed: %s", exc)
            return []
        return [WebResult(title=i.get("title", ""), url=i.get("link", ""),
                          snippet=i.get("snippet", ""), provider=self.name)
                for i in data.get("items", [])[:k]]


class WebSearchAdapter:
    """Holds the config-selected provider and exposes a uniform ``search``."""

    def __init__(self, provider: WebSearchProvider, config: ResearchConfig | None = None) -> None:
        self.provider = provider
        self.config = config or ResearchConfig()

    @property
    def enabled(self) -> bool:
        return self.provider.name != "disabled"

    def search(self, query: str, k: int | None = None) -> list[WebResult]:
        return self.provider.search(query, k or self.config.max_results)

    @classmethod
    def from_settings(cls, settings, config: ResearchConfig | None = None) -> "WebSearchAdapter":
        cfg = config or ResearchConfig.from_settings(settings)
        provider = _make_provider(cfg, settings)
        return cls(provider, cfg)


def _make_provider(cfg: ResearchConfig, settings=None) -> WebSearchProvider:
    p = cfg.provider.lower()
    if p == "wikipedia":
        return WikipediaProvider()
    if p == "duckduckgo":
        return DuckDuckGoProvider()
    if p == "tavily" and cfg.api_key:
        return TavilyProvider(cfg.api_key)
    if p == "google" and cfg.api_key and cfg.google_cx:
        return GoogleProvider(cfg.api_key, cfg.google_cx)
    if p == "local" and settings is not None:
        folder = settings.abspath("data/research/cache")
        return LocalCacheProvider(folder)
    return DisabledProvider()
