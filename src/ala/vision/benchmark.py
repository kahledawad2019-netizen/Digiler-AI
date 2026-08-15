"""Stage 17 — Vision-RAG benchmark on the **real corpus** (no mocks).

Lifts real ``Figure N:`` / ``Table N:`` captions from the corpus text layer,
ingests them as page-anchored ``IMAGE_CAPTION`` resources into an **isolated**
index (production untouched), and evaluates **figure retrieval** (a caption span
must retrieve its own figure) plus figure-type distribution and page-anchored
image citations. Vision encoder / BLIP captioner are config-selected seams; this
measures the offline caption-and-embed path that needs no vision model.
"""

from __future__ import annotations

import json
import random
import tempfile
from collections import Counter
from pathlib import Path

from ala.config.settings import Settings


def run_vision_benchmark(settings: Settings, *, n_resources: int = 140, seed: int = 0,
                         out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage17_vision")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="ala_vision_"))
    stg, ingestor, prod_store, catalog = _isolated(settings, tmp)
    try:
        rids = _source_resources(settings, n_resources)
        by_kind: Counter = Counter()
        n_figures = n_children = res_with_figs = 0
        timings: list[float] = []
        fig_chunks: list[tuple[str, str, int, str]] = []   # (chunk_id, text, page, resource_id)
        example_citation = {}
        from ala.retrieval.chunking.store import ChunkStore
        iso_store = ChunkStore(stg.derived_path)

        for rid in rids:
            outcome = ingestor.ingest_figures(rid)
            if not outcome.ok:
                continue
            res_with_figs += 1
            n_figures += outcome.n_figures
            n_children += outcome.n_children
            timings.append(outcome.total_ms)
            texts = iso_store.load_text(outcome.resource_id, "child")
            for m in iso_store.load_meta(outcome.resource_id, "child"):
                txt = texts.get(m.chunk_id, "")
                if txt:
                    fig_chunks.append((m.chunk_id, txt, m.page, outcome.resource_id))
                    by_kind[_kind_of(txt)] += 1

        # figure retrieval eval (label-free known-item over caption spans)
        rng = random.Random(seed)
        sample = rng.sample(fig_chunks, min(60, len(fig_chunks)))
        hit1 = hit3 = mrr = 0.0
        bm25 = ingestor._incremental.bm25_index
        for cid, text, _page, _rid in sample:
            words = text.split()
            span = " ".join(words[len(words) // 3: len(words) // 3 + 7])
            ranked = [h[0] for h in bm25.search(span, top_k=10)]
            if cid in ranked:
                r = ranked.index(cid)
                hit1 += r == 0
                hit3 += r < 3
                mrr += 1.0 / (r + 1)
        k = max(1, len(sample))

        # page-anchored image citation for one figure that has a page
        paged = next((fc for fc in fig_chunks if fc[2] is not None), fig_chunks[0] if fig_chunks else None)
        if paged:
            example_citation = _citation(stg, catalog, iso_store, paged[0], paged[3])

        payload = {
            "source_resources_scanned": len(rids), "resources_with_figures": res_with_figs,
            "n_figures": n_figures, "n_image_chunks": n_children,
            "by_kind": dict(by_kind),
            "retrieval": {"n": len(sample), "hit@1": round(hit1 / k, 4),
                          "hit@3": round(hit3 / k, 4), "mrr": round(mrr / k, 4)},
            "mean_ingest_ms": round(sum(timings) / len(timings), 1) if timings else 0.0,
            "citation": example_citation,
        }
    finally:
        ingestor.close()
        catalog.close()

    (out / "vision.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    from ala.vision import viz
    viz.render_all(payload, figs)
    (out / "VISION.md").write_text(_markdown(payload), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
def _source_resources(settings: Settings, n: int) -> list[str]:
    derived = settings.derived_path
    return [f.parent.parent.name
            for f in sorted(derived.glob("*/chunks/children.text.jsonl"))[:n]]


def _kind_of(text: str) -> str:
    t = text[:12].lower()
    for k in ("table", "diagram", "chart", "screenshot", "figure"):
        if k in t:
            return k
    return "figure"


def _isolated(settings: Settings, tmp: Path):
    from ala.catalog.repository import KnowledgeCatalog
    from ala.graph.store import GraphStore
    from ala.ingestion.pipeline import IngestionPipeline
    from ala.registry.registry import ResourceRegistry
    from ala.retrieval.bm25.index import BM25Index
    from ala.retrieval.chunking.service import ChunkingService
    from ala.retrieval.chunking.store import ChunkStore
    from ala.retrieval.embedding.factory import get_embedder
    from ala.retrieval.embedding.pipeline import EmbeddingService
    from ala.retrieval.vectorstore.indexer import VectorIndexer
    from ala.retrieval.vectorstore.qdrant_store import QdrantVectorStore
    from ala.research.ingest import IncrementalIngestor
    from ala.vision.ingest import VisionIngestor
    from ala.vision.models import VisionConfig

    stg = settings.model_copy(update={"paths": settings.paths.model_copy(update={
        "derived_dir": str(tmp / "derived"), "raw_dir": str(tmp / "raw"),
        "catalog_db": str(tmp / "catalog.db")})})
    reg = ResourceRegistry.from_settings(stg)
    emb = get_embedder("hashing")
    vs = QdrantVectorStore(":memory:", "vision_bench"); vs.ensure_collection(emb.dim)
    incr = IncrementalIngestor(
        stg, pipeline=IngestionPipeline.default(stg), chunking=ChunkingService(stg, reg),
        embedding=EmbeddingService(stg, embedder=emb, registry=reg, vector_store=None),
        vector_indexer=VectorIndexer(stg, vs, "hashing", registry=reg),
        bm25_index=BM25Index(), bm25_path=tmp / "bm25",
        graph_store=GraphStore(tmp / "graph.db"), embedder=emb,
        chunk_store=ChunkStore(stg.derived_path))
    prod_store = ChunkStore(settings.derived_path)          # read real figure text from production
    ingestor = VisionIngestor(stg, config=VisionConfig(), incremental=incr, registry=reg,
                              source_store=prod_store)
    return stg, ingestor, prod_store, KnowledgeCatalog.from_settings(stg)


def _citation(stg, catalog, store, chunk_id, rid) -> dict:
    from ala.explorer.explorer import CitationExplorer
    from ala.explorer.resolver import CitationResolver
    from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage
    meta = next((m for m in store.load_meta(rid, "child") if m.chunk_id == chunk_id), None)
    if meta is None:
        return {}
    item = EvidenceItem(rank=0, chunk_id=chunk_id, text="figure", retrieval_score=0.9,
                        confidence=0.9, resource_id=meta.resource_id, page=meta.page,
                        source_type="pdf", citation="")
    idx = CitationExplorer(CitationResolver(stg, catalog)).build(
        EvidencePackage(query="figure", normalized_query="figure", items=[item]))
    n = idx.nodes[0]
    return {"locator": n.locator, "link": n.link, "resolvable": n.resolvable}


def _markdown(p: dict) -> str:
    r = p["retrieval"]; c = p["citation"]
    return "\n".join([
        "# Stage 17 — Vision RAG: Benchmark",
        "",
        f"Scanned **{p['source_resources_scanned']}** corpus resources → "
        f"**{p['resources_with_figures']}** had captioned figures/tables → "
        f"**{p['n_figures']} figures** → **{p['n_image_chunks']} image blocks** indexed.",
        "",
        f"By kind: {p['by_kind']}",
        "",
        "## Figure retrieval (caption span → its own figure)",
        "",
        "| metric | value |",
        "|---|---|",
        f"| queries | {r['n']} |",
        f"| Hit@1 | **{r['hit@1']}** |",
        f"| Hit@3 | {r['hit@3']} |",
        f"| MRR | {r['mrr']} |",
        f"| mean ingest / resource | {p['mean_ingest_ms']} ms |",
        "",
        "## Page-anchored image citation",
        f"- locator **{c.get('locator')}** · link `{c.get('link')}` (resolvable {c.get('resolvable')})",
        "",
        "## Figures (`figures/`)",
        "`vision_pipeline` · `figure_type_distribution` · `retrieval_quality` · `ingest_timeline`.",
        "",
        "## Honest notes",
        "- The offline path is **caption-and-embed**: real figure/table captions from the corpus "
        "text layer become searchable `IMAGE_CAPTION` blocks (page-anchored). True cross-modal "
        "retrieval (CLIP image vectors) and image captioning (BLIP) are real, config-selected seams "
        "that require the optional vision deps (not installed here).",
        "- Figures without an inline text caption (a bare `Figure 1` reference) are skipped — only "
        "genuinely described figures/tables are indexed. Retrieval is a label-free caption-span task.",
        "",
    ])
