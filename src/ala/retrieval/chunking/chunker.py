"""Stage 2 — Parent-Child chunking.

Two-level, structure-aware:
  * **Parents** are the *context* units: consecutive DIR blocks grouped by their
    structural key (same section / same slide / same notebook cell / same video
    window), bounded by ``parent_target_tokens``. A parent is what the LLM
    ultimately reads.
  * **Children** are the *match* units: each parent is recursively split into
    overlapping ``child_target_tokens`` windows on multilingual-safe sentence
    boundaries. Children are what get embedded and searched.

Every child references its parent, resource, page/slide/timestamp, section and
heading (inherited from its structural parent) — so citations survive and there
are **no orphans** (every child has a parent; every parent has >= 1 child).
"""

from __future__ import annotations

from ala.fabric.content import BlockType, ContentBlock
from ala.fabric.learning_resource import LearningResource
from ala.retrieval.chunking.config import ChunkingConfig
from ala.retrieval.chunking.models import (
    Chunk,
    ChunkKind,
    ChunkMetadata,
    ChunkSet,
    ChunkType,
)
from ala.retrieval.chunking.splitter import RecursiveTextSplitter
from ala.retrieval.chunking.tokenizer import TokenCounter, WordTokenCounter
from ala.retrieval.dir import DocumentIR, build_document_ir

_TIME_WINDOW_SEC = 180  # video transcript window when grouping by timestamp

_BLOCKTYPE_TO_CHUNKTYPE = {
    BlockType.TABLE.value: ChunkType.TABLE,
    BlockType.CODE.value: ChunkType.CODE,
    BlockType.PARAGRAPH.value: ChunkType.PARAGRAPH,
    BlockType.LIST.value: ChunkType.PARAGRAPH,
}


class ParentChildChunker:
    def __init__(
        self,
        config: ChunkingConfig | None = None,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self.config = config or ChunkingConfig()
        self.counter = token_counter or WordTokenCounter()
        self.parent_splitter = RecursiveTextSplitter(
            self.config.parent_target_tokens, overlap_tokens=0, counter=self.counter
        )
        self.child_splitter = RecursiveTextSplitter(
            self.config.child_target_tokens,
            overlap_tokens=self.config.child_overlap_tokens,
            counter=self.counter,
        )

    # ------------------------------------------------------------------ #
    def chunk(self, source: LearningResource | DocumentIR) -> ChunkSet:
        ir = source if isinstance(source, DocumentIR) else build_document_ir(source)
        rid = ir.resource_id
        enrich = _enrichment(ir)

        groups = self._group_into_parents(ir.blocks)
        parents: list[Chunk] = []
        children: list[Chunk] = []
        child_seq = 0

        for pidx, group in enumerate(groups):
            parent_id = f"{rid}::p{pidx:04d}"
            ptext = "\n\n".join(b.text for b in group if b.text.strip()).strip()
            if not ptext:
                continue
            cite = _citation_context(group)
            ctype = _chunk_type(group)

            child_texts = self._split_children(ptext)
            child_ids: list[str] = []
            for ctext in child_texts:
                child_id = f"{rid}::c{child_seq:05d}"
                child_seq += 1
                child_ids.append(child_id)
                children.append(
                    Chunk(
                        text=ctext,
                        metadata=ChunkMetadata(
                            chunk_id=child_id, parent_id=parent_id, resource_id=rid,
                            kind=ChunkKind.CHILD, order=child_seq,
                            language=cite["language"], token_count=self.counter.count(ctext),
                            chunk_type=ctype, source_block_ids=cite["block_ids"],
                            **cite["anchor"], **enrich,
                        ),
                    )
                )

            parents.append(
                Chunk(
                    text=ptext,
                    metadata=ChunkMetadata(
                        chunk_id=parent_id, parent_id=None, resource_id=rid,
                        kind=ChunkKind.PARENT, order=pidx, child_ids=child_ids,
                        language=cite["language"], token_count=self.counter.count(ptext),
                        chunk_type=ctype, source_block_ids=cite["block_ids"],
                        **cite["anchor"], **enrich,
                    ),
                )
            )

        return ChunkSet(resource_id=rid, parents=parents, children=children)

    # ------------------------------------------------------------------ #
    def _group_into_parents(self, blocks: list[ContentBlock]) -> list[list[ContentBlock]]:
        groups: list[list[ContentBlock]] = []
        cur: list[ContentBlock] = []
        cur_key = None
        cur_tokens = 0
        for block in blocks:
            if not block.text.strip():
                continue
            key = _parent_key(block)
            btok = self.counter.count(block.text)
            over = cur and (cur_tokens + btok > self.config.parent_target_tokens)
            if cur and (key != cur_key or over):
                groups.append(cur)
                cur, cur_tokens = [], 0
            cur.append(block)
            cur_key = key
            cur_tokens += btok
        if cur:
            groups.append(cur)
        return groups

    def _split_children(self, ptext: str) -> list[str]:
        parts = self.child_splitter.split(ptext) or [ptext]
        # Merge a tiny trailing child into the previous one (avoid orphan slivers).
        if len(parts) > 1 and self.counter.count(parts[-1]) < self.config.min_chunk_tokens:
            parts[-2] = parts[-2] + " " + parts[-1]
            parts.pop()
        return parts


# --------------------------------------------------------------------------- #
def _parent_key(block: ContentBlock):
    a = block.anchor
    if a.slide is not None:
        return ("slide", a.slide)
    if a.cell is not None:
        return ("cell", a.cell)
    if a.t_start is not None:
        return ("time", int(a.t_start // _TIME_WINDOW_SEC))
    return ("section", tuple(block.section_path))


def _citation_context(group: list[ContentBlock]) -> dict:
    pages = [b.anchor.page for b in group if b.anchor.page is not None]
    slides = [b.anchor.slide for b in group if b.anchor.slide is not None]
    starts = [b.anchor.t_start for b in group if b.anchor.t_start is not None]
    section_path = group[0].section_path
    langs = [b.language for b in group if b.language]
    language = max(set(langs), key=langs.count) if langs else "en"
    return {
        "language": language,
        "block_ids": [b.block_id for b in group],
        "anchor": {
            "section_path": list(section_path),
            "heading": section_path[-1] if section_path else None,
            "page": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "slide": slides[0] if slides else None,
            "timestamp": min(starts) if starts else None,
        },
    }


def _chunk_type(group: list[ContentBlock]) -> ChunkType:
    if any(b.anchor.slide is not None for b in group):
        return ChunkType.SLIDE
    if any(b.anchor.cell is not None for b in group):
        return ChunkType.NOTEBOOK_CELL
    if any(b.anchor.t_start is not None for b in group):
        return ChunkType.TRANSCRIPT
    non_heading = [b for b in group if b.type != BlockType.HEADING.value]
    types = {b.type for b in non_heading}
    if len(non_heading) == 1 and len(types) == 1:
        return _BLOCKTYPE_TO_CHUNKTYPE.get(next(iter(types)), ChunkType.OTHER)
    if any(b.type == BlockType.HEADING.value for b in group):
        return ChunkType.SECTION
    if len(types) == 1:
        return _BLOCKTYPE_TO_CHUNKTYPE.get(next(iter(types)), ChunkType.MIXED)
    return ChunkType.MIXED


def _enrichment(ir: DocumentIR) -> dict:
    m = ir.metadata
    return {
        "topics": list(m.topics),
        "keywords": list(m.pedagogy.keywords),
        "prerequisites": list(m.pedagogy.prerequisites),
        "concepts": list(m.retrieval.concepts),
        "learning_objectives": list(m.pedagogy.learning_objectives),
    }
