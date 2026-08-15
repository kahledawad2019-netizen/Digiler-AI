"""Stage 9 — Evidence Package.

The structured, cited object the LLM consumes instead of raw retrieval output.
Turns ranked ``RetrievalResult``s into rich, validated, serializable evidence
with typed citations (PDF page / slide / video timestamp / web) — the foundation
of the Citation Explorer and GraphRAG grounding.
"""

from ala.retrieval.evidence.builder import EvidenceBuilder
from ala.retrieval.evidence.formatter import EvidenceFormatter
from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage, SourceType
from ala.retrieval.evidence.serializer import EvidenceSerializer
from ala.retrieval.evidence.validator import EvidenceValidator, EvidenceValidationResult

__all__ = [
    "EvidenceBuilder",
    "EvidencePackage",
    "EvidenceItem",
    "SourceType",
    "EvidenceFormatter",
    "EvidenceSerializer",
    "EvidenceValidator",
    "EvidenceValidationResult",
]
