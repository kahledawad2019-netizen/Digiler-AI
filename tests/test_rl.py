"""Stage 21 — RL Adaptive Learning tests."""

from __future__ import annotations

from ala.config.settings import load_settings
from ala.rl.bandit import LinUCB
from ala.rl.benchmark import _eval_context, _gain, _train
from ala.rl.controller import AdaptiveController
from ala.rl.environment import SimulatedLearner
from ala.rl.models import RLConfig
from ala.rl.reward import RewardModel
from ala.rl.store import RLStore
from ala.student.model import StudentModel
from ala.student.models import StudentConfig
from ala.student.store import StudentStore


# -- bandit ----------------------------------------------------------------- #
def test_linucb_select_update_and_persist():
    b = LinUCB(3, 2, alpha=0.5)
    assert 0 <= b.select([0.5, 1.0]) < 3
    b.update(1, [0.5, 1.0], reward=1.0)
    assert b.counts[1] == 1
    b2 = LinUCB.from_dict(b.to_dict())
    assert b2.n_arms == 3 and b2.counts == b.counts


def test_linucb_learns_best_arm():
    # arm 2 always pays 1, others 0 → greedy should converge to arm 2
    b = LinUCB(3, 2, alpha=0.2)
    for _ in range(60):
        a = b.select([1.0, 1.0])
        b.update(a, [1.0, 1.0], reward=1.0 if a == 2 else 0.0)
    assert b.select([1.0, 1.0], explore=False) == 2


# -- reward ----------------------------------------------------------------- #
def test_reward_shaping():
    rm = RewardModel(RLConfig())
    good = rm.compute(correct=True, mastery_gain=0.1, response_time=5)
    bad = rm.compute(correct=False, mastery_gain=0.0, response_time=25,
                     repeat_mistake=True, skipped_prerequisite=True)
    assert good > 0 > bad


# -- simulated learner ------------------------------------------------------ #
def test_learner_gain_peaks_in_zpd():
    zpd = _gain(0.5, 0.45)                                  # difficulty near ability
    assert zpd > _gain(0.5, 0.05) and zpd > _gain(0.5, 0.95)


def test_learner_answer_and_learning():
    learner = SimulatedLearner({"c": 0.4}, seed=0)
    correct, rt, gain = learner.answer("c", 0.4)
    assert isinstance(correct, bool) and rt > 0 and gain >= 0
    assert learner.ability["c"] >= 0.4                     # practice increases ability


# -- contextual policy actually learns (mini benchmark) --------------------- #
def test_contextual_bandit_beats_fixed():
    cfg = RLConfig()
    bandit, curve = _train(cfg, rounds=1500, seed=0)
    grid = [round(0.12 + 0.04 * i, 3) for i in range(19)]
    ctx = _eval_context(bandit, cfg.difficulties, grid)
    assert ctx["rl"]["regret"] < ctx["fixed-medium"]["regret"]
    assert ctx["rl"]["regret"] < ctx["always-easy"]["regret"]
    assert ctx["rl"]["mean_reward"] > 0.6                  # close to oracle (~0.88)


# -- controller integration ------------------------------------------------- #
def test_controller_adapts_and_persists(tmp_path):
    settings = load_settings(None)
    sm = StudentModel(settings, store=StudentStore(tmp_path / "s.db"), config=StudentConfig())
    sm.get_or_create("u")
    ctrl = AdaptiveController(settings, sm, config=RLConfig(),
                             store=RLStore(tmp_path / "rl"))
    learner = SimulatedLearner({"concept:x": 0.3}, seed=1)
    try:
        choice = ctrl.choose_difficulty("u", "concept:x")
        assert "difficulty" in choice and choice["action"]
        correct, rt, _ = learner.answer("concept:x", choice["difficulty"])
        it = ctrl.record_outcome("u", "concept:x", choice, correct=correct, response_time=rt)
        assert it.reward != 0.0 and it.mastery_after != it.mastery_before
        assert (tmp_path / "rl" / "u.json").is_file()       # policy persisted
        # explanation-style + question-type are separate bandits
        assert ctrl.choose("u", "concept:x", decision="explanation_style")["action"] \
            in RLConfig().explanation_styles
    finally:
        ctrl.close()
