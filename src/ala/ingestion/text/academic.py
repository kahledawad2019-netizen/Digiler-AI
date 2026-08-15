"""Academic structure detection.

Detects the course→module→week→lecture→section→topic→subtopic hierarchy plus
examples / exercises / assignments / labs / references from a resource's blocks.
Cues and patterns are injected from config (no hardcoded rules), so the parser
is tunable per corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ala.fabric.content import BlockType
from ala.fabric.learning_resource import LearningResource
from ala.ingestion.config import AcademicConfig


@dataclass
class AcademicStructure:
    week: int | None = None
    lecture: str | None = None
    sections: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    subtopics: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    exercises: list[str] = field(default_factory=list)
    assignments: list[str] = field(default_factory=list)
    labs: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "week": self.week, "lecture": self.lecture,
            "sections": self.sections, "topics": self.topics, "subtopics": self.subtopics,
            "examples": self.examples, "exercises": self.exercises,
            "assignments": self.assignments, "labs": self.labs, "references": self.references,
        }


class AcademicStructureDetector:
    def __init__(self, config: AcademicConfig | None = None) -> None:
        self.config = config or AcademicConfig()
        self._week = [re.compile(p, re.IGNORECASE) for p in self.config.week_patterns]
        self._lecture = [re.compile(p, re.IGNORECASE) for p in self.config.lecture_patterns]

    def detect(self, resource: LearningResource) -> AcademicStructure:
        s = AcademicStructure()
        hay = [resource.metadata.title] + [b.text for b in resource.blocks]

        s.week = self._first_int(self._week, hay)
        lecture_no = self._first_int(self._lecture, hay)
        if lecture_no is not None:
            s.lecture = str(lecture_no)

        for block in resource.blocks:
            text = block.text.strip()
            if block.type == BlockType.HEADING.value:
                level = int(block.meta.get("level", len(block.section_path) or 1))
                s.sections.append(text)
                (s.topics if level <= 2 else s.subtopics).append(text)
            self._match_cues(text, s)

        # de-duplicate while preserving order
        for name in ("sections", "topics", "subtopics", "examples",
                     "exercises", "assignments", "labs", "references"):
            setattr(s, name, _dedupe(getattr(s, name)))
        return s

    def _match_cues(self, text: str, s: AcademicStructure) -> None:
        low = text.lower()
        label = text[:80]
        for cue in self.config.example_cues:
            if cue in low:
                s.examples.append(label)
                break
        for cue in self.config.exercise_cues:
            if cue in low:
                s.exercises.append(label)
                break
        for cue in self.config.assignment_cues:
            if cue in low:
                s.assignments.append(label)
                break
        for cue in self.config.lab_cues:
            if cue in low:
                s.labs.append(label)
                break
        for cue in self.config.reference_cues:
            if cue in low:
                s.references.append(label)
                break

    @staticmethod
    def _first_int(patterns: list[re.Pattern], texts: list[str]) -> int | None:
        for text in texts:
            for pat in patterns:
                m = pat.search(text or "")
                if m:
                    try:
                        return int(m.group(1))
                    except (ValueError, IndexError):
                        continue
        return None


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
