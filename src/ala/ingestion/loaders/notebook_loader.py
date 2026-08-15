"""Jupyter notebook loader (.ipynb).

Markdown cells are parsed with the shared Markdown parser (preserving headings /
lists / tables); code cells become CODE blocks anchored by cell index. Outputs
are ignored (this milestone extracts source structure only).
"""

from __future__ import annotations

from pathlib import Path

from ala.core.enums import DocType, ExtractionMethod
from ala.fabric.content import Anchor, BlockType
from ala.ingestion.loaders.base import BaseLoader, BlockSpec
from ala.ingestion.loaders.markdown_parse import parse_markdown_blocks


class NotebookLoader(BaseLoader):
    name = "notebook"
    extensions = (".ipynb",)
    doc_types = (DocType.NOTEBOOK.value,)
    extraction_method = ExtractionMethod.NATIVE_TEXT
    requires = ("nbformat",)

    def _parse(self, path: Path) -> list[BlockSpec]:
        import nbformat

        nb = nbformat.read(str(path), as_version=4)
        specs: list[BlockSpec] = []
        for idx, cell in enumerate(nb.get("cells", [])):
            src = cell.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            if not src.strip():
                continue
            if cell.get("cell_type") == "markdown":
                for spec in parse_markdown_blocks(src):
                    spec.anchor = Anchor(cell=idx)
                    specs.append(spec)
            elif cell.get("cell_type") == "code":
                specs.append(
                    BlockSpec(
                        text=src,
                        block_type=BlockType.CODE,
                        anchor=Anchor(cell=idx),
                        meta={"language": nb.get("metadata", {})
                              .get("kernelspec", {}).get("language", "python")},
                    )
                )
        return specs
