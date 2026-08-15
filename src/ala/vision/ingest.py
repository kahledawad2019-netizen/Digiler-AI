"""VisionIngestor — figures / images → searchable, page-anchored resources.

``ingest_figures`` lifts a resource's ``Figure N:`` captions into a companion
figures resource; ``ingest_image`` handles a standalone image. Both build a real
raw artifact + metadata and reuse ``IncrementalIngestor.ingest_resource`` for the
chunk→embed→Qdrant→BM25→graph downstream (no pipeline duplicated). Image evidence
then rides the same retriever, GraphRAG and Citation Explorer as text.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from ala.config.settings import Settings
from ala.core import ids
from ala.core.enums import DocType, Role
from ala.vision.figures import FigureExtractor
from ala.vision.loader import FigureArtifactLoader, ImageLoader
from ala.vision.models import VisionConfig


@dataclass
class VisionOutcome:
    resource_id: str
    n_figures: int
    n_children: int
    timings_ms: dict = field(default_factory=dict)
    total_ms: float = 0.0
    searchable: bool = False
    ok: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class VisionIngestor:
    def __init__(self, settings: Settings, *, config: VisionConfig | None = None,
                 incremental=None, registry=None, source_store=None) -> None:
        self.settings = settings
        self.config = config or VisionConfig.from_settings(settings)
        self._incremental = incremental
        self._registry = registry
        self._source_store = source_store

    # -- figures from an existing resource ------------------------------- #
    def ingest_figures(self, source_rid: str, *, module: str = "fig") -> VisionOutcome:
        figures = self.extract_figures(source_rid)
        if not figures:
            return VisionOutcome("", 0, 0, {}, 0.0, False, False)

        dest = self.settings.raw_path / self.config.track / self.config.course / module
        dest.mkdir(parents=True, exist_ok=True)
        art = dest / f"{ids.slugify(source_rid)[:60]}.figures.jsonl"
        art.write_text("\n".join(json.dumps({"kind": f.kind, "number": f.number,
                       "caption": f.caption, "page": f.page, "source": f.source_resource})
                       for f in figures), encoding="utf-8")

        reg = self._registry or self._make_registry()
        meta = reg.build_metadata(art, track=self.config.track, course=self.config.course,
                                  module=module, title=f"Figures: {source_rid}",
                                  doc_type=DocType.REFERENCE, role=Role.REFERENCE,
                                  language="en", update=True, strict=False)
        resource = FigureArtifactLoader().load(art, meta)
        reg.commit(resource.metadata)
        outcome = (self._incremental or self._make_incremental()).ingest_resource(resource)
        return VisionOutcome(outcome.resource_id, len(figures), outcome.n_children,
                             outcome.timings_ms, outcome.total_ms, outcome.ok, outcome.ok)

    def extract_figures(self, source_rid: str):
        from ala.retrieval.chunking.store import ChunkStore
        store = self._source_store or ChunkStore(self.settings.derived_path)
        metas = {m.chunk_id: m for m in store.load_meta(source_rid, "child")}
        texts = store.load_text(source_rid, "child")
        mt = [(m.page, source_rid, texts.get(cid, "")) for cid, m in metas.items()]
        return FigureExtractor(self.config).extract_from_chunks(mt)

    # -- a standalone image ---------------------------------------------- #
    def ingest_image(self, path: str | Path, *, title: str | None = None,
                     module: str = "img") -> VisionOutcome:
        p = Path(path)
        reg = self._registry or self._make_registry()
        meta = reg.build_metadata(p, track=self.config.track, course="images", module=module,
                                  title=title or p.stem, doc_type=DocType.OTHER,
                                  role=Role.MATERIAL, language="en", update=True, strict=False)
        resource = ImageLoader(self.config).load(p, meta)
        reg.commit(resource.metadata)
        outcome = (self._incremental or self._make_incremental()).ingest_resource(resource)
        return VisionOutcome(outcome.resource_id, 1, outcome.n_children,
                             outcome.timings_ms, outcome.total_ms, outcome.ok, outcome.ok)

    # ------------------------------------------------------------------ #
    def _make_registry(self):
        from ala.registry.registry import ResourceRegistry
        self._registry = ResourceRegistry.from_settings(self.settings)
        return self._registry

    def _make_incremental(self):
        from ala.research.ingest import IncrementalIngestor
        self._incremental = IncrementalIngestor.from_settings(self.settings)
        return self._incremental

    def close(self) -> None:
        if self._registry is not None:
            self._registry.close()
