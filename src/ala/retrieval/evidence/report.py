"""Stage 9 report — benchmark evidence-package creation + generate figures."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

from ala.config.settings import Settings
from ala.retrieval.evidence import viz
from ala.retrieval.evidence.serializer import EvidenceSerializer
from ala.retrieval.evidence.service import EvidenceService
from ala.retrieval.evidence.validator import EvidenceValidator

_DEFAULT_QUERIES = [
    "How do convolutional neural networks use pooling layers?",
    "What is a foreign key and referential integrity?",
    "Explain overfitting and regularization in deep learning",
    "What is the difference between primary key and foreign key?",
    "How does K-means clustering assign points to clusters?",
]


def run_report(settings: Settings, queries: list[str] | None = None, *,
               top_k: int = 8, out_dir: str | Path | None = None) -> Path:
    queries = queries or _DEFAULT_QUERIES
    validator = EvidenceValidator()
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage9_evidence")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    rows = []
    first_package = None
    service = EvidenceService(settings)
    try:
        for q in queries:
            tracemalloc.start()
            t0 = time.perf_counter()
            pkg = service.build(q, top_k=top_k)
            build_ms = (time.perf_counter() - t0) * 1000
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            size = EvidenceSerializer.size_bytes(pkg)
            valid = validator.validate(pkg)
            rows.append({
                "query": q, "items": len(pkg.items),
                "overall_confidence": pkg.overall_confidence,
                "build_ms": round(build_ms, 1), "peak_kb": round(peak / 1024, 1),
                "serialized_bytes": size, "valid": valid.ok,
                "errors": len(valid.errors), "warnings": len(valid.warnings),
            })
            if first_package is None:
                first_package = pkg
    finally:
        service.close()

    # figures
    viz.pipeline_diagram(figs / "evidence_pipeline.png")
    if first_package is not None:
        viz.evidence_breakdown(first_package, figs / "evidence_breakdown.png")
        EvidenceSerializer.save(first_package, out / "sample_package.json")

    (out / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "README.md").write_text(_markdown(rows), encoding="utf-8")
    return out


def _markdown(rows: list[dict]) -> str:
    avg_ms = round(sum(r["build_ms"] for r in rows) / len(rows), 1) if rows else 0
    avg_size = round(sum(r["serialized_bytes"] for r in rows) / len(rows)) if rows else 0
    lines = [
        "# Stage 9 — Evidence Package: Benchmark & Validation",
        "",
        f"{len(rows)} queries · mean build **{avg_ms} ms** · mean serialized size "
        f"**{avg_size} bytes** · all packages valid: **{all(r['valid'] for r in rows)}**.",
        "",
        "| query | items | confidence | build_ms | peak_kb | bytes | valid |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['query'][:48]} | {r['items']} | {r['overall_confidence']} | "
                     f"{r['build_ms']} | {r['peak_kb']} | {r['serialized_bytes']} | {r['valid']} |")
    lines += [
        "",
        "## Figures",
        "- ![pipeline](figures/evidence_pipeline.png)",
        "- ![breakdown](figures/evidence_breakdown.png)",
        "",
        "`sample_package.json` is a full serialized Evidence Package.",
        "",
    ]
    return "\n".join(lines)
