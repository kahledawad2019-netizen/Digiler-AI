# Stage 21 — RL Adaptive Learning

A contextual-bandit **online-policy** layer (NOT LLM training). It observes the
learner's state (concept mastery, recent accuracy, response time) and adapts **quiz
difficulty**, **explanation style** and **question type** to maximise learning gain,
with reward shaping (correct / fast / mastery-gain; penalties for repeated mistakes,
forgetting, skipped prerequisites). Integrates with the Student Model (Stage 18) —
every update advances mastery. Fully **additive**. Package:
[`src/ala/rl/`](../src/ala/rl/).

## Why a contextual bandit

The *optimal* quiz difficulty depends on the learner's current mastery (the
**context**): too easy teaches nothing, too hard frustrates — learning peaks in the
**zone of proximal development**. A context-free fixed policy can't be right for
everyone; a **contextual** policy that maps mastery → difficulty can. LinUCB is the
canonical online algorithm — no gradients, no LLM.

## Components

- **LinUCB** ([bandit.py](../src/ala/rl/bandit.py)) — per-arm ridge regression + an
  upper-confidence-bound exploration bonus; serialisable state (persists per learner).
- **RewardModel** ([reward.py](../src/ala/rl/reward.py)) — correct + **mastery gain**
  (the true learning signal) + speed − penalties (repeated mistakes / forgetting /
  skipped prerequisites).
- **AdaptiveController** ([controller.py](../src/ala/rl/controller.py)) — observes the
  Student-Model state, chooses difficulty / explanation-style / question-type, records
  the outcome through the Student Model (advancing mastery) and updates the policy.
- **SimulatedLearner** ([environment.py](../src/ala/rl/environment.py)) — an IRT
  simulator used only to **evaluate** the policy (no real users).
- **RLStore** — per-learner policy persistence.

## What it adapts

quiz **difficulty** · **explanation style** (concise / balanced / detailed /
example-driven) · **question type** (recall / application / conceptual) · and the
adaptive **learning path** (`next_concept`, the weakest concept). Each is its own
contextual bandit sharing the learner context `[mastery, recent_accuracy, attempts,
bias]`.

## CLI

```powershell
ala rl --student ada --concept concept:gradient-descent          # show adaptive choices
ala rl --student ada --concept concept:gradient-descent --quiz correct --time 8
ala rl --benchmark
```

## Configuration (`config/platform.yaml → rl`)

`alpha` (exploration) · graded `difficulties` · `explanation_styles` ·
`question_types` · `location` · `reward` weights.

## Benchmark (contextual bandit vs baselines; simulated learner — no mocks)

`reports/stage21_rl/`.

**Contextual policy quality** (learners arrive at varying mastery — the setting a
contextual bandit is built for):

| policy | mean learning-reward | regret vs oracle |
|---|---|---|
| oracle | 0.882 | 0.000 |
| **RL** | **0.715** | **0.167** |
| fixed-medium | 0.400 | 0.482 |
| always-easy | 0.410 | 0.471 |
| always-hard | 0.175 | 0.707 |
| random | 0.411 | 0.470 |

**RL beats every fixed / random policy on regret** — it learns to match difficulty to
mastery (see `difficulty_mapping.png`: chosen difficulty rises with the learner's
mastery, tracking the oracle's ZPD).

**Learning trajectory** (apply the policy to one learner):

| policy | final mastery | rounds to 0.7 |
|---|---|---|
| oracle | 1.00 | 7 |
| **RL** | **1.00** | **10** |
| always-easy | 0.885 | 28 |
| fixed-medium | 0.931 | 72 |
| always-hard | 0.173 | 120 |

RL reaches mastery as fast as the oracle and far faster than any fixed policy; the
real `AdaptiveController` + Student Model run reaches mastery **0.99** in 40
interactions and persists the policy.

## Visualizations

`learning_curves` · `policy_comparison` · `contextual_regret` · `difficulty_mapping`
· `training_curve` (online convergence toward the oracle).

## Tests

[`tests/test_rl.py`](../tests/test_rl.py) — LinUCB select/update/persist + learns the
best arm, reward shaping, ZPD gain peak + learner dynamics, **the contextual bandit
beats fixed policies on regret**, and controller integration (adapts + updates mastery
+ persists). Full suite **209 passed**.

## Limitations (honest)

- The learner is a **simulator** (IRT: P(correct)=σ(k·(mastery−difficulty)); learning
  peaks in the ZPD). This is the standard way to evaluate an online policy with no real
  users — the bandit, reward and comparison are real. Real-learner validation needs a
  deployment study.
- A **contextual bandit is myopic** (maximises immediate learning reward). This suits
  "pick the best next question given the learner's state"; a single learner climbing
  over a long horizon is a sequential (MDP) problem — the bandit handles it well here
  because the immediate-optimal action (ZPD) also drives long-term progress.
- Non-zero regret (0.167) reflects **discrete arms** + a linear-quadratic value model
  approximating the continuous oracle; finer arms shrink it.
- In deployment the reward uses the **observable** mastery-gain from the Student Model
  (difficulty-scaled), not the simulator's hidden gain.

## Extension hooks

- **Study Planner (20):** the policy tunes the plan's difficulty mix + revision gap.
- **Quiz Agent (22):** calls `choose_*` to pick the next question, then `record_outcome`.
- **Review scheduler:** a second bandit over review timing (spaced repetition) using the
  same store.
