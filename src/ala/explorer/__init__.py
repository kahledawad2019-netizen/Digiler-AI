"""Stage 15 — Citation Explorer.

A unified, navigable view over the citations already carried by the Evidence
Package (Stage 9), graph evidence (Stage 11/12) and web evidence (Stage 14).
Resolves every citation to a clickable deep link (PDF page, slide, notebook,
video timestamp, web URL, or concept/graph origin), groups them by source,
supports filtering, and exports a self-contained clickable HTML explorer + the
citation-accuracy report. Fully additive — it reads existing structures, it does
not change them.
"""

from ala.explorer.explorer import CitationExplorer
from ala.explorer.models import (CitationIndex, CitationNode, ExplorerConfig,
                                  SourceRecord)
from ala.explorer.resolver import CitationResolver
from ala.explorer.service import CitationExplorerService

__all__ = [
    "CitationExplorer", "CitationResolver", "CitationExplorerService",
    "CitationIndex", "CitationNode", "SourceRecord", "ExplorerConfig",
]
