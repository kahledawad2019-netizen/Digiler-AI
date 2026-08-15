"""Resource Fabric — the unified internal representation of every resource.

Architecture V3 §1: "one ingestion spine, many source adapters, one evidence
model." This package defines the ONE object every loader converges to
(``LearningResource``) so the rest of the platform never cares whether a
resource began life as a PDF, a slide deck, a notebook, a YouTube transcript, or
a web page.

    raw source ──(SourceAdapter)──▶ LearningResource ──▶ chunker/embedder/graph
"""

from ala.fabric.content import Anchor, BlockType, ContentBlock
from ala.fabric.learning_resource import LearningResource
from ala.fabric.adapters import SourceAdapter, PlainTextAdapter

__all__ = [
    "LearningResource",
    "ContentBlock",
    "BlockType",
    "Anchor",
    "SourceAdapter",
    "PlainTextAdapter",
]
