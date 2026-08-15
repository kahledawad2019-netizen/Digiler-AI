"""FigureExtractor — lift figure/table/diagram captions from the corpus text layer.

Offline and real: lecture PDFs already carry ``Figure 3: …`` / ``Table 1: …``
captions as text. This detects them (with the source page from the chunk anchor),
classifies the kind, and yields ``Figure`` records that become searchable
``IMAGE_CAPTION`` blocks — so a diagram/table is retrievable and citable by page,
without any vision model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ala.vision.models import ImageKind, VisionConfig

_MARK = re.compile(r"\b(figure|fig|table|diagram|chart|exhibit|plot|graph)\s*\.?\s*"
                   r"(\d+(?:\.\d+)?)\s*[:.\)-]?\s*", re.IGNORECASE)
_KIND = {"figure": ImageKind.FIGURE, "fig": ImageKind.FIGURE, "exhibit": ImageKind.FIGURE,
         "table": ImageKind.TABLE, "diagram": ImageKind.DIAGRAM, "chart": ImageKind.CHART,
         "plot": ImageKind.CHART, "graph": ImageKind.CHART}


@dataclass
class Figure:
    fig_id: str                  # "<resource>#figure-3"
    kind: str
    number: str
    caption: str
    source_resource: str
    page: int | None = None

    def block_text(self) -> str:
        return f"[{self.kind}] {self.kind.title()} {self.number}: {self.caption}"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class FigureExtractor:
    def __init__(self, config: VisionConfig | None = None) -> None:
        self.config = config or VisionConfig()

    def extract(self, text: str, *, source_resource: str = "", page: int | None = None) -> list[Figure]:
        cfg = self.config
        out: list[Figure] = []
        for m in _MARK.finditer(text or ""):
            kind = _KIND.get(m.group(1).lower(), ImageKind.FIGURE).value
            number = m.group(2)
            tail = text[m.end(): m.end() + cfg.max_caption_chars]
            caption = re.split(r"\n|(?<=[.!?])\s", tail.strip(), maxsplit=1)[0]
            caption = " ".join(caption.split()).strip(" .:-")
            if len(caption.split()) >= cfg.min_caption_words and not _MARK.fullmatch(caption or "x"):
                out.append(Figure(
                    fig_id=f"{source_resource}#{kind}-{number}", kind=kind, number=number,
                    caption=caption[: cfg.max_caption_chars], source_resource=source_resource,
                    page=page))
        return out

    def extract_from_chunks(self, metas_texts) -> list[Figure]:
        """metas_texts: iterable of (page, resource_id, text) → deduped figures."""
        seen: set = set()
        figures: list[Figure] = []
        for page, rid, text in metas_texts:
            for fig in self.extract(text, source_resource=rid, page=page):
                key = (fig.source_resource, fig.kind, fig.number, fig.caption[:40])
                if key not in seen:
                    seen.add(key)
                    figures.append(fig)
        return figures
