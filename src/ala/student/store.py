"""StudentStore — SQLite persistence for the learner profile (separate from the KB).

Three tables: ``students`` (profile), ``concept_mastery`` (per-student per-concept),
``events`` (longitudinal history). Nothing here touches the knowledge catalog — the
learner's data lives in its own database (V3: student state is not resource state).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ala.core.clock import utcnow_iso
from ala.student.models import ConceptMastery, LearningEvent, StudentProfile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY, name TEXT, level TEXT, preferred_language TEXT,
    explanation_style TEXT, difficulty_preference TEXT, learning_pace TEXT,
    goals_json TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS concept_mastery (
    student_id TEXT, concept_id TEXT, mastery REAL, attempts INTEGER, correct INTEGER,
    last_seen TEXT, PRIMARY KEY (student_id, concept_id)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, type TEXT, ref TEXT,
    concepts_json TEXT, score REAL, difficulty REAL, timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_mastery_student ON concept_mastery(student_id);
CREATE INDEX IF NOT EXISTS idx_events_student ON events(student_id);
"""


class StudentStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: safe under sqlite3 SERIALIZED mode (threadsafety=3);
        # the API layer builds/closes this store across threadpool workers.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    # -- profile --------------------------------------------------------- #
    def upsert_profile(self, p: StudentProfile) -> None:
        p.updated_at = utcnow_iso()
        self._conn.execute(
            "INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(student_id) DO UPDATE SET name=excluded.name, level=excluded.level, "
            "preferred_language=excluded.preferred_language, explanation_style=excluded.explanation_style, "
            "difficulty_preference=excluded.difficulty_preference, learning_pace=excluded.learning_pace, "
            "goals_json=excluded.goals_json, updated_at=excluded.updated_at",
            (p.student_id, p.name, p.level, p.preferred_language, p.explanation_style,
             p.difficulty_preference, p.learning_pace, json.dumps(p.goals),
             p.created_at, p.updated_at))
        self._conn.commit()

    def get_profile(self, student_id: str) -> StudentProfile | None:
        r = self._conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
        if r is None:
            return None
        return StudentProfile(
            student_id=r["student_id"], name=r["name"], level=r["level"],
            preferred_language=r["preferred_language"], explanation_style=r["explanation_style"],
            difficulty_preference=r["difficulty_preference"], learning_pace=r["learning_pace"],
            goals=json.loads(r["goals_json"] or "[]"),
            created_at=r["created_at"], updated_at=r["updated_at"])

    # -- mastery --------------------------------------------------------- #
    def get_mastery(self, student_id: str, concept_id: str) -> ConceptMastery | None:
        r = self._conn.execute("SELECT * FROM concept_mastery WHERE student_id=? AND concept_id=?",
                               (student_id, concept_id)).fetchone()
        return ConceptMastery(r["concept_id"], r["mastery"], r["attempts"], r["correct"],
                              r["last_seen"]) if r else None

    def set_mastery(self, student_id: str, cm: ConceptMastery) -> None:
        self._conn.execute(
            "INSERT INTO concept_mastery VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(student_id, concept_id) DO UPDATE SET mastery=excluded.mastery, "
            "attempts=excluded.attempts, correct=excluded.correct, last_seen=excluded.last_seen",
            (student_id, cm.concept_id, cm.mastery, cm.attempts, cm.correct, cm.last_seen))
        self._conn.commit()

    def all_mastery(self, student_id: str) -> list[ConceptMastery]:
        rows = self._conn.execute("SELECT * FROM concept_mastery WHERE student_id=?",
                                  (student_id,)).fetchall()
        return [ConceptMastery(r["concept_id"], r["mastery"], r["attempts"], r["correct"],
                               r["last_seen"]) for r in rows]

    # -- events ---------------------------------------------------------- #
    def add_event(self, e: LearningEvent) -> None:
        self._conn.execute(
            "INSERT INTO events(student_id,type,ref,concepts_json,score,difficulty,timestamp) "
            "VALUES (?,?,?,?,?,?,?)",
            (e.student_id, e.type, e.ref, json.dumps(e.concept_ids), e.score, e.difficulty,
             e.timestamp))
        self._conn.commit()

    def list_events(self, student_id: str, *, kind: str | None = None) -> list[LearningEvent]:
        q = "SELECT * FROM events WHERE student_id=?"
        args: list = [student_id]
        if kind:
            q += " AND type=?"; args.append(kind)
        q += " ORDER BY id"
        return [LearningEvent(r["student_id"], r["type"], r["ref"],
                              json.loads(r["concepts_json"] or "[]"), r["score"],
                              r["difficulty"], r["timestamp"])
                for r in self._conn.execute(q, args).fetchall()]

    def close(self) -> None:
        self._conn.close()

    @classmethod
    def from_settings(cls, settings) -> "StudentStore":
        from ala.student.models import StudentConfig
        return cls(settings.abspath(StudentConfig.from_settings(settings).location))
