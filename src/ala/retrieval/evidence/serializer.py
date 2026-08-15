"""EvidenceSerializer — JSON persistence + size measurement for evidence packages."""

from __future__ import annotations

import json
from pathlib import Path

from ala.retrieval.evidence.models import EvidencePackage


class EvidenceSerializer:
    @staticmethod
    def to_json(package: EvidencePackage, *, indent: int | None = 2) -> str:
        return json.dumps(package.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> EvidencePackage:
        return EvidencePackage.from_dict(json.loads(text))

    @staticmethod
    def save(package: EvidencePackage, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(EvidenceSerializer.to_json(package), encoding="utf-8")
        return p

    @staticmethod
    def load(path: str | Path) -> EvidencePackage:
        return EvidenceSerializer.from_json(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def size_bytes(package: EvidencePackage) -> int:
        return len(EvidenceSerializer.to_json(package, indent=None).encode("utf-8"))
