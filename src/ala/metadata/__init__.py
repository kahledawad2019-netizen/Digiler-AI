"""Resource metadata: the professional schema + sidecar + validation."""

from ala.metadata.schema import (
    ResourceMetadata,
    FileInfo,
    SourceInfo,
    ProvenanceInfo,
    PedagogyInfo,
    StatusInfo,
    LifecycleInfo,
    RetrievalInfo,
    SCHEMA_VERSION,
)

__all__ = [
    "ResourceMetadata",
    "FileInfo",
    "SourceInfo",
    "ProvenanceInfo",
    "PedagogyInfo",
    "StatusInfo",
    "LifecycleInfo",
    "RetrievalInfo",
    "SCHEMA_VERSION",
]
