"""Stage 15 — Citation Explorer benchmark (real corpus, no mocks).

Runs GraphRAG over real questions, builds the citation index for each, and
measures citation resolution, locator coverage, confidence and composition.
Exports a clickable HTML explorer for one example.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ala.config.settings import Settings
from ala.explorer.service import CitationExplorerService

_QUERIES = [
    "what is a convolutional neural network", "explain gradient descent",
    "what is a foreign key in a relational database", "how does k-means clustering work",
    "what is a probability distribution", "explain overfitting and regularization",
    "what is a random forest", "how does backpropagation work",
    "what is a support vector machine", "explain principal component analysis",
]


def run_explorer_benchmark(settings: Settings, *, out_dir: str | Path | None = None,
                           example: str = "what is a convolutional neural network") -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage15_citation_explorer")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    svc = CitationExplorerService(settings)
    try:
        svc.graphrag.answer("warmup", top_k=5)
        by_type: Counter = Counter()
        by_kind: Counter = Counter()
        resolvable, locator, conf, per_query = [], [], [], []
        for q in _QUERIES:
            idx = svc.explore(q, top_k=8)
            st = idx.stats()
            for k, v in st["by_source_type"].items():
                by_type[k] += v
            for k, v in st["by_kind"].items():
                by_kind[k] += v
            resolvable.append(st["resolvable_rate"]); locator.append(st["locator_coverage"])
            conf.append(st["mean_confidence"])
            per_query.append({"query": q, **st})

        example_index = svc.explore(example, top_k=8)
        html_path = out / "example_explorer.html"
        from ala.explorer.html import render
        html_path.write_text(render(example_index, title=f"Citation Explorer — {example}"),
                             encoding="utf-8")
    finally:
        svc.close()

    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0
    payload = {
        "n_queries": len(_QUERIES),
        "total_citations": sum(by_kind.values()),
        "by_source_type": dict(by_type), "by_kind": dict(by_kind),
        "resolvable_rate": mean(resolvable), "locator_coverage": mean(locator),
        "mean_confidence": mean(conf), "per_query": per_query,
        "example": example_index.to_dict(), "html": str(html_path),
    }
    (out / "citation_explorer.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    from ala.explorer import viz
    viz.render_all(payload, example_index, figs)
    (out / "CITATION_EXPLORER.md").write_text(_markdown(payload), encoding="utf-8")
    return out


def _markdown(p: dict) -> str:
    return "\n".join([
        "# Stage 15 — Citation Explorer: Report",
        "",
        f"Real corpus, **{p['n_queries']} queries**, **{p['total_citations']} citations** indexed.",
        "",
        "## Citation accuracy",
        "",
        "| metric | value |",
        "|---|---|",
        f"| resolvable rate (deep link works) | {p['resolvable_rate']} |",
        f"| locator coverage (page/slide/timestamp) | {p['locator_coverage']} |",
        f"| mean citation confidence | {p['mean_confidence']} |",
        f"| by source type | {p['by_source_type']} |",
        f"| by kind | {p['by_kind']} |",
        "",
        "## Clickable explorer",
        f"- `{Path(p['html']).name}` — self-contained HTML: filter by kind/source-type, "
        "click any citation to open the PDF page / slide / video timestamp / web URL.",
        "",
        "## Figures (`figures/`)",
        "`citation_distribution` · `citation_accuracy` · `evidence_composition` · `citation_flow`.",
        "",
        "## Honest notes",
        "- *Resolvable* = the cited resource's raw file exists and a deep link (with page/slide/"
        "timestamp fragment) can be built; it does not re-verify that the PDF page shows the exact "
        "sentence (that needs a PDF renderer). Locator coverage is the fraction of chunk citations "
        "that carry a page/slide/timestamp.",
        "- Slide/notebook fragments (`#slide=`, cells) are conventions most viewers ignore; the file "
        "still opens. Video timestamps use `#t=` (browser/YouTube convention).",
        "",
    ])
