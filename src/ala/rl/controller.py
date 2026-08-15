"""AdaptiveController — the online-policy layer wired to the Student Model.

Observes the learner's state (mastery + recent accuracy + attempts), chooses an
adaptive **quiz difficulty** / **explanation style** / **question type** with a
contextual bandit, and — on the outcome — records the quiz through the Student
Model (advancing mastery) and updates the policy with the shaped reward. Persists
the policy per learner. Also proposes an adaptive **learning path** (next concept).
"""

from __future__ import annotations

from ala.rl.bandit import LinUCB
from ala.rl.models import Interaction, RLConfig
from ala.rl.reward import RewardModel
from ala.rl.store import RLStore
from ala.student.model import StudentModel

_DIM = 4                       # [mastery, recent_accuracy, attempts, bias]


class AdaptiveController:
    def __init__(self, settings, student_model: StudentModel, *, graph=None,
                 config: RLConfig | None = None, store: RLStore | None = None) -> None:
        self.settings = settings
        self.sm = student_model
        self.graph = graph
        self.config = config or RLConfig.from_settings(settings)
        self.reward = RewardModel(self.config)
        self.store = store or RLStore.from_settings(settings)
        self._cache: dict[str, dict[str, LinUCB]] = {}

    # -- policy per learner --------------------------------------------- #
    def _bandits(self, student_id: str) -> dict[str, LinUCB]:
        if student_id not in self._cache:
            loaded = self.store.load(student_id)
            labels = self.config.difficulty_labels[:len(self.config.difficulties)] or \
                [f"d{d}" for d in self.config.difficulties]
            self._cache[student_id] = loaded or {
                "difficulty": LinUCB(len(self.config.difficulties), _DIM, alpha=self.config.alpha,
                                     arms=labels),
                "explanation_style": LinUCB(len(self.config.explanation_styles), _DIM,
                                            alpha=self.config.alpha, arms=self.config.explanation_styles),
                "question_type": LinUCB(len(self.config.question_types), _DIM,
                                        alpha=self.config.alpha, arms=self.config.question_types)}
        return self._cache[student_id]

    def context(self, student_id: str, concept_id: str) -> list[float]:
        mastery = self.sm.mastery_of(student_id, concept_id)
        recent = [e.score for e in self.sm.store.list_events(student_id)
                  if concept_id in e.concept_ids and e.score is not None][-5:]
        acc = sum(recent) / len(recent) if recent else 0.5
        return [mastery, acc, min(1.0, len(recent) / 5.0), 1.0]

    # -- decisions ------------------------------------------------------- #
    def choose(self, student_id: str, concept_id: str, *, decision: str = "difficulty",
               explore: bool = True) -> dict:
        x = self.context(student_id, concept_id)
        bandit = self._bandits(student_id)[decision]
        arm = bandit.select(x, explore=explore)
        out = {"decision": decision, "action_index": arm, "action": bandit.arms[arm], "context": x}
        if decision == "difficulty":
            out["difficulty"] = self.config.difficulties[arm]
        return out

    def choose_difficulty(self, student_id: str, concept_id: str, **kw) -> dict:
        return self.choose(student_id, concept_id, decision="difficulty", **kw)

    # -- feedback -------------------------------------------------------- #
    def record_outcome(self, student_id: str, concept_id: str, choice: dict, *, correct: bool,
                       response_time: float = 0.0, repeat_mistake: bool = False,
                       skipped_prerequisite: bool = False) -> Interaction:
        difficulty = choice.get("difficulty", 0.5)
        before = self.sm.mastery_of(student_id, concept_id)
        self.sm.record_quiz(student_id, [concept_id], correct=correct, difficulty=difficulty)
        after = self.sm.mastery_of(student_id, concept_id)
        gain = after - before
        reward = self.reward.compute(correct=correct, mastery_gain=gain, response_time=response_time,
                                     repeat_mistake=repeat_mistake,
                                     skipped_prerequisite=skipped_prerequisite)
        bandits = self._bandits(student_id)
        bandits[choice["decision"]].update(choice["action_index"], choice["context"], reward)
        self.store.save(student_id, bandits)
        return Interaction(
            concept_id=concept_id, context=choice["context"], decision=choice["decision"],
            action=choice["action"], action_index=choice["action_index"], correct=correct,
            response_time=response_time, mastery_before=round(before, 4),
            mastery_after=round(after, 4), reward=reward)

    # -- adaptive learning path ----------------------------------------- #
    def next_concept(self, student_id: str) -> str | None:
        weak = self.sm.weak_concepts(student_id)
        return weak[0].concept_id if weak else None

    def close(self) -> None:
        self.sm.close()
