"""Stage 17 — Vision RAG.

Makes figures, tables, diagrams, charts and screenshots retrievable by turning
them into text-carrying ``IMAGE_CAPTION`` blocks (caption + OCR + structured
metadata) that flow through the *existing* pipeline (DIR → embedding → graph →
GraphRAG). Two paths: (1) an offline-real **FigureExtractor** that lifts
``Figure N:`` / ``Table N:`` captions from the real corpus text layer with page
anchors; (2) an **ImageLoader** for standalone images (caption via BLIP, text via
tesseract OCR, cross-modal vectors via CLIP — all config-selected seams). Additive
— image evidence reuses the same retriever, citations and Citation Explorer.
"""

from ala.vision.figures import Figure, FigureExtractor
from ala.vision.ingest import VisionIngestor
from ala.vision.loader import ImageLoader
from ala.vision.models import ImageKind, VisionConfig

__all__ = [
    "FigureExtractor", "Figure", "VisionIngestor", "ImageLoader",
    "VisionConfig", "ImageKind",
]
