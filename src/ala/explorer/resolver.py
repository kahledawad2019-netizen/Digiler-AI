"""CitationResolver — turn a citation into a clickable deep link + locator.

Resolves the source resource to its raw file via the catalog and builds a
navigable link with the right fragment per modality: PDF ``#page=N``, slide
``#slide=N``, video ``#t=SECONDS``; web citations link to their URL; concept
citations link to their graph node (``concept:<id>``) for graph navigation.
"""

from __future__ import annotations

from ala.config.settings import Settings
from ala.explorer.models import CitationNode


class CitationResolver:
    def __init__(self, settings: Settings, catalog=None) -> None:
        self.settings = settings
        self.catalog = catalog
        self._cache: dict[str, object] = {}

    def _meta(self, rid: str):
        if not rid or self.catalog is None:
            return None
        if rid not in self._cache:
            self._cache[rid] = self.catalog.get(rid)
        return self._cache[rid]

    def resolve(self, node: CitationNode) -> CitationNode:
        if node.kind == "concept":
            cid = node.concept_id
            node.link = cid if cid.startswith("concept:") else f"concept:{cid}"
            node.resolvable = bool(cid)
            return node
        if node.kind == "web":
            node.resolvable = bool(node.link)                # link pre-set to the URL
            return node

        meta = self._meta(node.resource_id)
        if meta is None:
            node.resolvable = False
            return node
        node.title = node.title or meta.title
        path = self.settings.abspath(meta.file.file_path)
        uri = path.as_uri() if path.exists() else ""
        frag = ""
        if node.page is not None:
            frag = f"#page={node.page}"
        elif node.slide is not None:
            frag = f"#slide={node.slide}"
        elif node.timestamp is not None:
            frag = f"#t={int(node.timestamp)}"
        node.link = (uri + frag) if uri else ""
        node.resolvable = bool(uri)
        return node
