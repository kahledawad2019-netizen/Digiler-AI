"""RLStore — persist a learner's bandit policies (per-student JSON)."""

from __future__ import annotations

import json
from pathlib import Path

from ala.rl.bandit import LinUCB


class RLStore:
    def __init__(self, location: str | Path) -> None:
        self.dir = Path(location)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, student_id: str) -> Path:
        return self.dir / f"{student_id}.json"

    def load(self, student_id: str) -> dict[str, LinUCB] | None:
        p = self._path(student_id)
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return {k: LinUCB.from_dict(v) for k, v in data.items()}

    def save(self, student_id: str, bandits: dict[str, LinUCB]) -> None:
        self._path(student_id).write_text(
            json.dumps({k: v.to_dict() for k, v in bandits.items()}, ensure_ascii=False),
            encoding="utf-8")

    @classmethod
    def from_settings(cls, settings) -> "RLStore":
        from ala.rl.models import RLConfig
        return cls(settings.abspath(RLConfig.from_settings(settings).location))
