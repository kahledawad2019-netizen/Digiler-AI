"""Retrieval engine (Milestone 4+).

Built strictly in the mandatory order:
    Stage 1  Document Intermediate Representation (DIR)  -> retrieval.dir
    Stage 2  Parent-Child Chunking                       -> retrieval.chunking
    Stage 3  Chunk Metadata                              -> retrieval.chunking.models
    Stage 4  Embedding Pipeline                          -> retrieval.embedding
    Stage 5  Hybrid Retrieval (dense + BM25 + RRF)       -> retrieval.search
    Stage 6  Knowledge Graph                             -> retrieval.graph
    Stage 7  Graph Retrieval
    Stage 8  Unified Retriever + Evidence Package

Nothing downstream of Stage 1 consumes raw extracted text — everything consumes
the DIR (a formalized view over the Resource Fabric's LearningResource).
"""

from ala.retrieval.dir import DocumentIR, Section, build_document_ir

__all__ = ["DocumentIR", "Section", "build_document_ir"]
