"""ResearchSessionLog — persist every research session (JSONL, append-only).

Records the question, confidence, whether the web was used, the ranked sources,
the user's approval decision, ingestion status and timing/statistics — the audit
trail behind Knowledge-Base growth (feeds the Stage 14 figures and future
Learning-Analytics dashboard).
"""

from __future__ import annotations

import json
from pathlib import Path

from ala.core.clock import utcnow_iso


class ResearchSessionLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> dict:
        record = {"timestamp": utcnow_iso(), **record}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def all(self) -> list[dict]:
        if not self.path.is_file():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def stats(self) -> dict:
        rows = self.all()
        used = [r for r in rows if r.get("used_web")]
        approved = [r for r in rows if r.get("approved")]
        return {
            "sessions": len(rows),
            "web_triggered": len(used),
            "approved": len(approved),
            "rejected": len(used) - len(approved),
            "resources_ingested": sum(len(r.get("ingested", [])) for r in rows),
        }

    @classmethod
    def from_settings(cls, settings) -> "ResearchSessionLog":
        return cls(settings.abspath("data/research/sessions.jsonl"))
