"""Stage 1 — Document Intermediate Representation (DIR).

The DIR is the single structured representation every downstream retrieval
component consumes. It is NOT a new storage model — the Resource Fabric's
``LearningResource`` + ``ContentBlock`` already hold the content; the DIR is a
formalized *view* over them that materializes the document's section hierarchy
(a tree) and exposes typed accessors for every structural element.

Why a view and not a new model: duplicating ContentBlock would violate the
"don't redesign / don't duplicate completed components" rule and create two
sources of truth. The one thing the flat block list lacks — a navigable section
tree — is what the chunker needs, so that is exactly what the DIR adds.

Field-coverage guarantee (the 18 required DIR fields → where they live):
    hierarchy .......... Section tree (built here) + block.section_path
    sections ........... Section nodes
    headings ........... BlockType.HEADING blocks
    paragraphs ......... BlockType.PARAGRAPH blocks
    bullet lists ....... BlockType.LIST blocks
    tables ............. BlockType.TABLE blocks
    figures ............ block.meta['images'] + BlockType.IMAGE_CAPTION
    captions ........... BlockType.IMAGE_CAPTION blocks
    equations .......... BlockType.EQUATION blocks
    code blocks ........ BlockType.CODE blocks
    hyperlinks ......... block.meta['links']
    page numbers ....... Anchor.page
    slide numbers ...... Anchor.slide
    timestamps ......... Anchor.t_start / t_end
    provenance ......... resource.metadata (source/provenance) + block_id (encodes resource_id)
    language ........... resource.metadata.language + block.language
    academic metadata .. resource.metadata.academic + section_path
    anchors ............ Anchor per block
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.fabric.content import Anchor, BlockType, ContentBlock
from ala.fabric.learning_resource import LearningResource


@dataclass
class Section:
    """A node in the document hierarchy: a heading and everything under it."""

    heading: str | None                     # None for the implicit root / preamble
    level: int                              # 0 = root, 1 = h1, ...
    path: list[str] = field(default_factory=list)   # breadcrumb of heading titles
    blocks: list[ContentBlock] = field(default_factory=list)   # direct content blocks
    children: list["Section"] = field(default_factory=list)    # nested subsections

    def iter_blocks(self):
        """Yield this section's blocks then its descendants' (reading order)."""
        yield from self.blocks
        for child in self.children:
            yield from child.iter_blocks()

    def text(self, sep: str = "\n\n") -> str:
        return sep.join(b.text for b in self.iter_blocks() if b.text.strip())


class DocumentIR:
    """Formal DIR view over a LearningResource.

    Holds a reference to the resource (single source of truth) plus a derived
    section tree. Provides typed accessors so no downstream code ever touches raw
    extracted text or reconstructs structure ad hoc.
    """

    def __init__(self, resource: LearningResource) -> None:
        self.resource = resource
        self.root = _build_section_tree(resource.blocks)

    # -- identity / provenance / language / academic --------------------- #
    @property
    def resource_id(self) -> str:
        return self.resource.resource_id

    @property
    def language(self) -> str:
        return self.resource.language

    @property
    def metadata(self):
        return self.resource.metadata

    @property
    def blocks(self) -> list[ContentBlock]:
        return self.resource.blocks

    @property
    def sections(self) -> list[Section]:
        """Top-level sections (children of the implicit root)."""
        return self.root.children

    # -- typed element accessors ----------------------------------------- #
    def by_type(self, block_type: BlockType) -> list[ContentBlock]:
        want = str(block_type)
        return [b for b in self.blocks if str(b.type) == want]

    def headings(self) -> list[ContentBlock]:
        return self.by_type(BlockType.HEADING)

    def paragraphs(self) -> list[ContentBlock]:
        return self.by_type(BlockType.PARAGRAPH)

    def lists(self) -> list[ContentBlock]:
        return self.by_type(BlockType.LIST)

    def tables(self) -> list[ContentBlock]:
        return self.by_type(BlockType.TABLE)

    def code_blocks(self) -> list[ContentBlock]:
        return self.by_type(BlockType.CODE)

    def equations(self) -> list[ContentBlock]:
        return self.by_type(BlockType.EQUATION)

    def captions(self) -> list[ContentBlock]:
        return self.by_type(BlockType.IMAGE_CAPTION)

    def figures(self) -> list[dict]:
        """Figure references: image sources + their captions (if any)."""
        figs: list[dict] = []
        for b in self.blocks:
            for src in b.meta.get("images", []) or []:
                figs.append({"src": src, "anchor": b.anchor.model_dump(exclude_none=True)})
        for cap in self.captions():
            figs.append({"caption": cap.text, "anchor": cap.anchor.model_dump(exclude_none=True)})
        return figs

    def hyperlinks(self) -> list[dict]:
        links: list[dict] = []
        for b in self.blocks:
            links.extend(b.meta.get("links", []) or [])
        return links

    def anchors(self) -> list[Anchor]:
        return [b.anchor for b in self.blocks]

    # -- coverage proof --------------------------------------------------- #
    def coverage(self) -> dict[str, bool]:
        """Report which DIR element categories are present (used by tests/UI)."""
        m = self.metadata
        return {
            "hierarchy": bool(self.sections) or bool(self.blocks),
            "sections": bool(self.sections),
            "headings": bool(self.headings()),
            "paragraphs": bool(self.paragraphs()),
            "lists": bool(self.lists()),
            "tables": bool(self.tables()),
            "figures": bool(self.figures()),
            "captions": bool(self.captions()),
            "equations": bool(self.equations()),
            "code": bool(self.code_blocks()),
            "hyperlinks": bool(self.hyperlinks()),
            "pages": any(b.anchor.page is not None for b in self.blocks),
            "slides": any(b.anchor.slide is not None for b in self.blocks),
            "timestamps": any(b.anchor.t_start is not None for b in self.blocks),
            "provenance": bool(m.provenance.extraction_method),
            "language": bool(m.language),
            "academic": m.week is not None or bool(m.topics) or m.academic is not None,
            "anchors": bool(self.blocks),
        }


def build_document_ir(resource: LearningResource) -> DocumentIR:
    return DocumentIR(resource)


# --------------------------------------------------------------------------- #
def _build_section_tree(blocks: list[ContentBlock]) -> Section:
    """Turn the flat, section_path-tagged block list into a hierarchy.

    Blocks carry a ``section_path`` breadcrumb (set by loaders). We fold that
    breadcrumb into a tree, attaching each block to the deepest section its path
    names, creating intermediate sections as needed.
    """
    root = Section(heading=None, level=0, path=[])
    index: dict[tuple[str, ...], Section] = {(): root}

    def ensure(path: tuple[str, ...]) -> Section:
        if path in index:
            return index[path]
        parent = ensure(path[:-1])
        node = Section(heading=path[-1], level=len(path), path=list(path))
        parent.children.append(node)
        index[path] = node
        return node

    for block in blocks:
        path = tuple(block.section_path)
        # A heading block *names* its own section; attach it to that section node.
        target = ensure(path)
        target.blocks.append(block)
    return root
