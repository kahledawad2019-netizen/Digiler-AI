# Stage 21 — RL Adaptive Learning: Benchmark

Contextual bandit (LinUCB, α=2.5, arms [0.2, 0.35, 0.5, 0.65, 0.8]). Learner is a labelled IRT simulator; policy + reward + comparison are real.

## Contextual policy quality (learners arrive at varying mastery)

| policy | mean learning-reward | regret vs oracle |
|---|---|---|
| oracle | 0.8818 | 0.0 |
| rl | 0.7152 | 0.1666 |
| fixed-medium | 0.4001 | 0.4817 |
| always-hard | 0.1754 | 0.7065 |
| always-easy | 0.4105 | 0.4714 |
| random | 0.4115 | 0.4703 |

**RL beats every fixed policy on regret:** True — the contextual bandit learns to match the difficulty to the learner's mastery; fixed policies can't.

## Learning trajectory (apply the policy to one learner)

| policy | final mastery | rounds to 0.7 |
|---|---|---|
| oracle | 1.0 | 7 |
| rl | 1.0 | 10 |
| fixed-medium | 0.9315 | 72 |
| always-hard | 0.1732 | 120 |
| always-easy | 0.8855 | 28 |
| random | 0.9956 | 23 |

**RL trajectory ≥ every fixed policy:** True — adapting difficulty upward as mastery grows lets the learner keep improving where fixed difficulties plateau.

## Adaptive integration (real AdaptiveController + Student Model)
- 40 interactions → mastery **0.9949**, policy persisted **True**; difficulty mix {'very-easy': 10, 'easy': 6, 'medium': 9, 'hard': 10, 'very-hard': 5}.

## Figures (`figures/`)
`learning_curves` · `policy_comparison` · `contextual_regret` · `difficulty_mapping` · `training_curve`.

## Honest notes
- The learner is a **simulator** (IRT: P(correct)=σ(k·(mastery−difficulty)); learning peaks in the zone of proximal development). This is the standard way to evaluate an online policy with no real users; the bandit, reward and comparison are real.
- A **contextual** bandit is the right tool because the optimal difficulty depends on the learner's mastery (the context) — so it beats every fixed policy. The **oracle** always targets the ZPD (an upper bound).
- Reward = the immediate learning gain (max in the ZPD), so the policy maximises learning, not mere correctness. In deployment the reward uses the observable mastery-gain from the Student Model (difficulty-scaled).
