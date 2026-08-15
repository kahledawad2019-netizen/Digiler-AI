"""Stage-4 evaluation report: benchmark models on real corpus chunks + figures.

Samples child chunks straight from the ingested corpus (``derived/*/chunks``),
benchmarks every *available* embedder (the hashing embedder always; transformer
models when sentence-transformers is installed and weights are present), writes a
Markdown report with the comparison table, and saves all figures. This is the
"evaluated + visualized" gate for Stage 4.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from ala.config.settings import Settings
from ala.retrieval.embedding import benchmark as bench
from ala.retrieval.embedding import viz
from ala.retrieval.embedding.factory import get_embedder, transformer_available


def sample_corpus_chunks(
    settings: Settings, sample_n: int = 300, per_resource_cap: int = 8, seed: int = 0
) -> tuple[list[str], list[str], list[str]]:
    """Return (texts, resource_ids, courses) sampled from ingested child chunks."""
    derived = settings.derived_path
    rng = random.Random(seed)
    texts: list[str] = []
    resource_ids: list[str] = []
    courses: list[str] = []
    resource_dirs = sorted(p for p in derived.glob("*") if (p / "chunks" / "children.text.jsonl").is_file())
    rng.shuffle(resource_dirs)
    for rdir in resource_dirs:
        rid = rdir.name
        course = rid.split(".")[1] if "." in rid else rid
        rows = [json.loads(l) for l in (rdir / "chunks" / "children.text.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()]
        rng.shuffle(rows)
        for row in rows[:per_resource_cap]:
            if row["text"].strip():
                texts.append(row["text"])
                resource_ids.append(rid)
                courses.append(course)
            if len(texts) >= sample_n:
                return texts, resource_ids, courses
    return texts, resource_ids, courses


def run_report(
    settings: Settings,
    model_keys: list[str] | None = None,
    *,
    sample_n: int = 300,
    out_dir: str | Path | None = None,
) -> Path:
    texts, resource_ids, courses = sample_corpus_chunks(settings, sample_n=sample_n)
    if not texts:
        raise RuntimeError("No ingested chunks found — run `ala ingest-dir --chunk` first.")

    keys = model_keys or _default_keys()
    embedders = []
    skipped = []
    for key in keys:
        if key != "hashing" and not transformer_available():
            skipped.append(key)
            continue
        embedders.append(get_embedder(key, hashing_dim=384))

    results = bench.compare_models(embedders, texts, labels=resource_ids, queries=texts[:10])

    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage4_embedding")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    # comparison chart + per-model projections (colored by course)
    comparison_path = viz.comparison_figure(results, figs / "model_comparison.png")
    made = [comparison_path]
    for emb, res in zip(embedders, results):
        vectors = emb.embed_documents(texts)
        tag = emb.model_id
        made.append(viz.pca_figure(vectors, courses, figs / f"pca_{tag}.png", f"PCA — {tag}"))
        made.append(viz.tsne_figure(vectors, courses, figs / f"tsne_{tag}.png", f"t-SNE — {tag}"))
        made.append(viz.umap_figure(vectors, courses, figs / f"umap_{tag}.png", f"UMAP — {tag}"))
        made.append(viz.cosine_heatmap(vectors, courses, figs / f"cosine_{tag}.png", f"Cosine — {tag}"))
        made.append(viz.distribution_figure(vectors, figs / f"dist_{tag}.png", f"Distribution — {tag}"))

    made = [m for m in made if m is not None]
    report_md = _render_markdown(results, texts, courses, skipped, made, out)
    (out / "README.md").write_text(report_md, encoding="utf-8")
    (out / "results.json").write_text(
        json.dumps([r.to_row() for r in results], indent=2), encoding="utf-8"
    )
    return out


def _default_keys() -> list[str]:
    return ["hashing", "minilm", "e5-small", "bge-m3"] if transformer_available() else ["hashing"]


def _render_markdown(results, texts, courses, skipped, figures, out: Path) -> str:
    n_courses = len(set(courses))
    lines = [
        "# Stage 4 — Embedding Pipeline: Benchmark & Evaluation",
        "",
        f"Sampled **{len(texts)} real child chunks** across **{n_courses} courses** "
        "from the ingested corpus.",
        "",
        "## Model comparison",
        "",
        bench.results_markdown(results),
        "",
        "Columns: `embed_s` steady-state embed time (model load excluded via warmup) · "
        "`texts/s` throughput · `compute_mb` peak Python allocation during embed · "
        "`bytes/vec` storage per vector · `query_ms` mean single-query latency · "
        "`coherence` = mean cosine(same-resource) − mean cosine(different-resource) · "
        "**`nn_purity`** = fraction of chunks whose nearest neighbour shares the same "
        "resource — a rank-based quality signal robust to each model's absolute cosine "
        "scale (the fairest cross-model comparison here). Latency reflects a CPU-only "
        "sandbox; a GPU would be 1–2 orders of magnitude faster.",
        "",
    ]
    if skipped:
        lines += [f"> Skipped (sentence-transformers not installed): {', '.join(skipped)}", ""]
    lines += ["## Figures", ""]
    for f in figures:
        rel = Path(f).relative_to(out).as_posix()
        lines.append(f"- ![{Path(f).stem}]({rel})")
    lines.append("")
    return "\n".join(lines)
