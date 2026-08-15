# AI Learning Platform — Architecture V3

**Status:** Proposed for freeze · **Supersedes:** Architecture v2 · **Incorporates v2 by reference** — anything marked *(unchanged: v2 §N)* is frozen as previously agreed.
**New in V3:** Concept Graph retrieval · Web-search fallback · Video learning module · unified Resource Fabric · revised agent/tool taxonomy · E8–E10 evaluations.

---

## 0. Chief-architect verdicts (read this before the details)

You asked for a critical review, not agreement. Here it is, requirement by requirement:

| Requirement | Verdict | One-line reason |
|---|---|---|
| R3 Video module | **Accept — highest value, lowest risk of the three** | Once "a video is just another document type," every existing capability (quiz, cards, graph, RL item bank) applies to it *for free*; timestamped citations are the best demo moment in the platform. |
| R1 Graph RAG | **Accept — but scoped, or it kills the project** | Full Microsoft-style GraphRAG is rejected with cost math (§4.6). A curriculum **Concept Graph** with three consumers (retrieval, Coach/RL, study-map UI) is accepted — three consumers is what makes it architecture instead of a buzzword. |
| R2 Web fallback | **Accept — with one guardrail you must explicitly own** | It breaks v2's absolute "no data leaves the device." The design is *local by default, web by consent* (§5.4). If you want silent auto-search, say so knowingly — it changes your privacy story in the defense. |
| R4 RL rethink | **Challenged; core survives with three upgrades** | Elo commitment, graph-grounded Coach, video-fed item bank (§7). Curriculum-RL re-examined now that a graph exists — still rejected; the graph fixes the state space, not the sample complexity. |

**Scope budget — the pushback you asked for.** V3 now contains: bilingual RAG, parent–child + hybrid retrieval, a concept graph, web fallback, video ingestion, a four-stage verifier, two RL policies, a student model, five task agents, and a ten-part evaluation campaign. That is a *lot* for one course project, even with six people. The design therefore includes a **pre-agreed cut list (§13.2)** — the order in which features get de-scoped if the schedule slips, decided now while we're calm, not in week 10 while panicking. The spine that is never cut: ingestion, retrieval core, Learning/Quiz/Flashcard, Verifier V0–V1, the quiz bandit, and the evaluation harness.

**Repo note (R3):** the provided repository (`maziyarpanahi/openmed`) is a third-party healthcare-NER/PII library, not a video summarizer and not authored by this team. §6 is designed from first principles; a reconciliation pass against the *actual* prior summarizer codebase is a pending action item once the correct link is provided. No design decision below depends on it.

---

## 1. The unifying idea: the Resource Fabric

Your goal — "a coherent platform, not a collection of techniques" — has a concrete architectural answer: **one ingestion spine, many source adapters, one evidence model.**

```
SOURCE ADAPTERS                    INGESTION SPINE (single pipeline)
─────────────────                  ──────────────────────────────────────────
PDF / DOCX / PPTX / TXT / image ─┐
YouTube URL  → transcript adapter ─┼→ structural parents → 256-tok children
Web page     → save-to-KB adapter ─┘   → embed (multilingual-e5) → ChromaDB
                                       → concept mining → graph update
                                       → parent docstore + metadata (SQLite)
```

Every resource — a lecture PDF, a pasted YouTube lecture, a web page the student chose to keep — becomes the **same thing** downstream: parents, children, concepts, provenance. Consequences:

- The Quiz, Flashcard, Summarization, and Learning agents need **zero video-specific or web-specific code**. They consume evidence; they don't care where it came from.
- Citations are uniform: `[doc, p.17]`, `[video 12:34]`, `[web: domain]` — one citation renderer, three anchor types.
- The Student Model's item bank and the Concept Graph grow automatically as resources are added, which is exactly what "the video permanently expands the student's knowledge base" means, implemented once instead of per-feature.

This is the coherence argument for the defense: *N features, one spine.* Everything in §§4–6 hangs off this.

---

## 2. System overview

```
                    ┌────────────────────────────────────────────┐
                    │                UI MODULES (§11)            │
                    │ Chat · Library · Study Map · Practice ·    │
                    │ Progress · Settings                        │
                    └───────────────────┬────────────────────────┘
                                        │
                     ┌──────────────────▼──────────────────┐
                     │      TIERED ROUTER (v2 §7, +web/    │
                     │      temporal cue detector, +GRAPH   │
                     │      structural-query intent)        │
                     └───────┬───────────────────┬─────────┘
                        META │                   │ task intents
                             ▼                   ▼
                    ┌───────────────┐   ┌────────────────────────────┐
                    │ Meta handler  │   │  TASK AGENTS (§8)          │
                    └───────────────┘   │ Learning · Summarize ·     │
                                        │ Quiz · Flashcard · Coach   │
                                        └──────────┬─────────────────┘
                                                   │ evidence request
                              ┌────────────────────▼─────────────────────┐
                              │   EVIDENCE ACQUISITION POLICY (§5)       │
                              │                                          │
                              │  KB arms:  dense ─┐                      │
                              │            BM25  ─┼→ RRF → sufficiency   │
                              │            graph ─┘        gate          │
                              │                              │           │
                              │              sufficient ─────┼─→ parents │
                              │              insufficient →  ▼           │
                              │              { refuse | OFFER WEB |      │
                              │                auto-web if opted in }    │
                              │                        │                 │
                              │              web tool (§5.3): search →   │
                              │              fetch → transient chunks →  │
                              │              tiered sources → merge      │
                              └────────────────────┬─────────────────────┘
                                                   │ labeled evidence [KB]/[Web]
                                        ┌──────────▼──────────┐
                                        │ GENERATOR (v2 §6)   │
                                        │ user's language     │
                                        └──────────┬──────────┘
                                        ┌──────────▼──────────┐
                                        │ VERIFIER (v2 §9 +   │
                                        │ §10 deltas)         │
                                        └──────────┬──────────┘
                                                   ▼
                                     verified answer, typed citations
                                                   │
        ┌──────────────────────┐                   │
        │ CONCEPT GRAPH (§4)   │◄── build/update ──┤ (ingestion side)
        │ SQLite + NetworkX    │──── retrieval ────┘ (query side)
        │                      │──── structure ───→ Coach / Study Map
        └──────────────────────┘
        ┌──────────────────────┐
        │ STUDENT MODEL (§9)   │◄── outcomes; feeds RL policies (§7)
        └──────────────────────┘
```

Unchanged and frozen from v2: embedder (multilingual-e5-small default / bge-m3 tier), generator tiers (Qwen2.5 family), chunking (256/32 children in 700–1,100-token structural parents), router mechanics, language policy, latency-tier discipline.

---

## 3. Knowledge base v3 *(delta on v2 §3)*

Two additions to the resource model:

**New `doc_type` values:** `video` (with `video_id`, `channel`, `url`, `t_start`, `t_end` per parent) and `web` (with `url`, `domain`, `fetched_at`, `source_tier`). Everything else in the v2 metadata schema applies unchanged — including the `embedder_version` stamp.

**Resource lifecycle field:** `persistence ∈ {permanent, session}`. KB documents and saved videos/pages are `permanent`; web evidence fetched during a fallback is `session` by default and lives in a session-scoped Chroma collection that is dropped on exit — unless the student clicks **"Add to my KB,"** which re-routes it through the full spine (including graph mining). One flag implements the entire "web knowledge merging" persistence question.

---

## 4. The Concept Graph (Graph RAG, scoped to survive local hardware)

### 4.1 What problem it actually solves (the anti-buzzword test)

Vector + BM25 retrieval answers *"where is this said?"* It cannot answer three things well:

1. **Multi-hop relational questions** — "How does dropout relate to the overfitting problem in the CNNs from week 3?" requires connecting evidence that never co-occurs in one chunk.
2. **Structural study questions** — "What should I learn before transformers?" is a *graph traversal*, not a retrieval.
3. **Prerequisite-aware coaching** — v2's Coach used a "prerequisite-readiness" heuristic *with no prerequisite data structure*. The graph is that missing structure.

Plus one UI consumer: the **Study Map** (concept graph rendered with the student's mastery overlaid) — the single most memorable screen in a defense demo. **One artifact, three consumers (retrieval, Coach/RL, UI).** That is the justification; if it served only retrieval, I would have pushed back harder.

### 4.2 What we build — a curriculum concept graph, not an everything-graph

- **Nodes:** course concepts only (~300–600 across the corpus). Not people, not dates, not generic entities — *concepts a student can master*. This scoping decision is what makes local extraction feasible and what makes the graph meaningful to the Student Model (its mastery table keys on these same nodes).
- **Edges (typed):** `prerequisite_of`, `part_of`, `related_to`, `contrasts_with` — plus provenance links `defined_in(parent_id)` / `discussed_in(parent_id)`. Every edge stores the parent(s) it was extracted from and a confidence score.

### 4.3 Build pipeline (two stages, LLM used surgically)

**G1 — Concept mining (no LLM, minutes).** Seed from `course.yaml` syllabus topics; mine candidates from parents by embedding-based keyphrase extraction (KeyBERT-style, reusing our embedder) + frequency/cohesion filters; canonicalize aliases by embedding clustering ("CNN" ↔ "convolutional neural network"); **one 30-minute human curation pass** in a simple admin table (a six-person team makes this a coffee-break task, and it's your quality firewall against extractor noise).

**G2 — Relation extraction (the only LLM stage).** For each parent containing ≥ 2 known concepts, one structured LLM call: given the parent text and its concept mentions, emit typed triples with confidence. Aggregate across parents (edge weight = evidence count), threshold low-confidence singleton edges.

**Cost math (the feasibility proof):** ~1,000 parents, ~70 % contain ≥ 2 concepts → ~700 calls × (~700 in / ~150 out) ≈ 0.6 M tokens. Mid-GPU 7B ≈ **40–60 min one-time**; CPU ≈ overnight, resumable, incremental for new resources (a new video adds ~10–20 calls). *(Estimates; the bench harness measures the real figure — E7.)*

### 4.4 Storage: SQLite + NetworkX. Not Neo4j.

Tables `concepts / aliases / edges / edge_provenance` in the same SQLite file as the Student Model; loaded into NetworkX in-memory at startup (600 nodes is nothing). **Neo4j rejected:** it's a server process — violating the in-process, zero-infra constraint that ChromaDB was chosen for. If the graph ever outgrows this, **Kùzu** (embedded, in-process graph DB, Cypher support) is the named growth path; adopting it now is complexity without need.

### 4.5 Graph retrieval and how it composes with the other arms

- **As a third retrieval arm (always on — it's ~milliseconds):** query → link to concepts (embedding similarity against node names+aliases, a 600-row matrix) → expand ego-graph ≤ 2 hops with edge-type weights → collect provenance parents → a third ranked list → **RRF fusion over {dense, BM25, graph}**. On single-hop factoids the graph arm contributes little and RRF naturally down-weights it; on multi-hop questions it surfaces the connecting parents that dense search structurally cannot.
- **As a native answerer for structural queries:** router detects "prerequisite/relationship/roadmap" intents (bilingual patterns + L2 prototypes) → answer composed from the graph itself, *citing edge provenance* — the graph never asserts a relationship it cannot point to a source for.
- **BM25 stays. Hybrid becomes more necessary, not less** — the graph adds relational recall but does nothing for exact-term/acronym matching (v2's code-switched-query argument is untouched), and dense remains the cross-lingual bridge. Three arms, three failure modes covered.

### 4.6 Classical vs Hybrid vs Graph — the comparison you asked for

| Query class | Classical (dense) | Hybrid (dense+BM25) | **Graph-augmented hybrid (V3)** |
|---|---|---|---|
| Single-hop factoid ("what is dropout?") | good | good | good (graph ≈ neutral) |
| Exact term / acronym / code-switched | weak | **strong** | strong |
| Cross-lingual (ar→en) | strong | strong (dense arm) | strong |
| Multi-hop relational | weak | weak | **strong** (connecting parents via edges) |
| Structural ("learn X before Y?") | none | none | **native** |
| Corpus-level synthesis | weak | weak | partial (Summarizer + metadata scoping covers most; community summaries deferred) |
| Index cost | low | low | +40–60 min GPU one-time |
| Query cost | ~10–25 ms | +1–5 ms | +~5–15 ms |

**Why full GraphRAG (Microsoft-style) is rejected, with numbers:** per-*chunk* extraction (~3,600 children) with gleaning re-prompts (~2×) plus community detection and community-summary generation ≈ 8–12× our G2 cost → multi-hour GPU / multi-day CPU indexing, executed by a 7B model whose extraction quality at that scale is the weakest link — and its headline benefit (corpus-global questions) is mostly covered by our Summarization agent with metadata scoping. We take the 20 % of GraphRAG that serves education (typed concept relations, provenance) and skip the 80 % that serves corpate document dumps. That sentence is the defense answer.

### 4.7 Citations through the graph

Unchanged citation contract: graph-sourced evidence cites the provenance parents `[doc, p.N]` / `[video 12:34]`; structural answers cite the edges' provenance. Nothing in the platform ever cites "the graph" as a source — the graph is an index over sources, and saying exactly that pre-empts the "is the graph hallucination-prone?" question.

---

## 5. Evidence Acquisition Policy — where web fallback lives

Web search is **not an agent and not a pipeline stage that always runs**. It is the third branch of a decision policy that already exists: v2's sufficiency gate.

### 5.1 Confidence estimation (reusing what we built)

The gate score combines: top fused-RRF score · count of children above the calibrated floor · parent diversity · graph-link strength (did the query link to any known concept at all — a strong out-of-syllabus signal). Calibrated on E1 + E5 into three zones: **answer** / **gray** / **insufficient**.

### 5.2 Trigger matrix

| Situation | Behavior |
|---|---|
| Gate = answer | Answer from KB. Web never touched. (The overwhelming majority of queries.) |
| Gate = gray | Answer from KB **with a hedge banner** + "Search the web to strengthen this?" button. |
| Gate = insufficient | v2 refusal, upgraded: "Your materials don't cover this. Nearest covered topics: … · **[Search the web]**". |
| Temporal/currency cues ("latest", years, version numbers — bilingual patterns at router) | KB still searched first (the syllabus may cover it), but the web offer is pre-armed and shown alongside any answer. |
| Student explicitly asks ("search online for…") | Direct to web path. |
| **Auto mode (Settings, off by default)** | Insufficient-zone queries go to web without asking. |

### 5.3 The web tool pipeline

`ddgs` (DuckDuckGo, keyless, zero-cost — honest note: unofficial and rate-limited; the backend is a swappable interface, and SearXNG/Brave/Tavily are named alternates) → top-5 results → **source tiering** (boost: official docs, *.edu, wikipedia, arXiv; demote/flag: forums, content farms) → fetch + `trafilatura` main-content extraction → **transient chunks** through the normal spine (session collection, §3) → evidence enters the same fusion, with `source_tier` exposed.

### 5.4 Merging, citations, conflicts, hallucination prevention

- **Labeled evidence:** every context block is tagged `[KB: doc, p.N]` or `[WEB: domain, date]`; the generation prompt *requires* per-claim source tags in the answer; the citation renderer shows visually distinct KB vs Web citations.
- **Conflict policy (stated, not improvised):** for course-definition questions ("what does *our* lecture define X as") KB outranks web; for currency questions web outranks KB; when both speak and disagree, the answer must *surface* the disagreement ("your lecture says A; current documentation says B") rather than silently pick — the Verifier's contradiction check enforces this.
- **Verification is source-blind:** web-sourced claims pass the same V2 entailment checks against their web evidence. The floor never moves: if neither KB nor web yields sufficient verified evidence, the system refuses. Parametric-knowledge answering remains off.
- **Privacy stance (the guardrail):** *local by default, web by consent.* The web button states plainly that the query text will be sent to an external search engine; auto mode is opt-in in Settings; every web call is logged in the interactions table. This preserves the platform's privacy story in a form you can defend: "student data never leaves the device **unless the student explicitly sends it**."

---

## 6. Video Learning Module

### 6.1 Design principle: a video is a document with timestamps

The entire module is **one source adapter** on the Resource Fabric plus one citation anchor type. There is no "video agent," no video-specific quiz generator, no separate video store. That absence is the design.

### 6.2 Pipeline

```
YouTube URL
  → 1. Caption path (fast, default): youtube-transcript-api
       — prefer human captions > auto-captions; Arabic tracks supported
  → 2. ASR fallback (no captions): yt-dlp audio → faster-whisper
       — CPU tier: small/int8 · GPU tier: large-v3
  → segment: chapter markers if present, else ~3-min windows snapped
    to sentence boundaries  → PARENTS (doc_type=video, t_start/t_end)
  → 256-tok children → embed → ChromaDB          (normal spine)
  → concept mining + incremental G2 (~10–20 LLM calls per lecture)
  → map-reduce segment summaries → a companion "overview note"
    resource (shown to the student AND itself indexed)
```

Latency, stated honestly *(estimates → E10 measures)*: caption path = seconds. ASR on a 60-min lecture ≈ 3–8 min on GPU (large-v3), ≈ 15–30 min on CPU (small/int8) — synchronous with a per-stage progress bar, and the UI says so before starting. The team already has production faster-whisper experience from prior work, which de-risks the only genuinely new dependency here.

### 6.3 What the student gets, and why it's free

Because the video became parents+children+concepts, the existing agents deliver everything R3 asked for with zero new generation code: **flashcards** (Flashcard agent scoped to the video's doc_id), **quizzes** (Quiz agent, ditto — and the new items enter the bandit's bank), **notes** (the overview note), **key concepts** (G1/G2 output, visible on the Study Map with provenance), and — the demo moment — **timestamped citations**: `[Video: Attention Is All You Need — lecture, 12:34]` deep-links to `&t=754s`. Ask a question in Arabic, get an Arabic answer citing minute 12 of an English YouTube lecture: that is the platform thesis in one interaction.

### 6.4 Boundaries and honesty

- Transcript quality is the ceiling: auto-captions on heavily accented or code-switched lectures degrade; `ocr_confidence` gets a sibling `asr_source ∈ {human_captions, auto_captions, whisper}` in metadata, surfaced in citations exactly like low-confidence OCR.
- Personal-study scope: transcripts are processed locally for the student's own KB; no redistribution — same data-rights note as Digilians materials, one sentence in the proposal.
- Reconciliation with the prior summarizer codebase is pending the correct repo link (§0); expected salvage: prompt patterns and any chaptering heuristics, not architecture.

---

## 7. Personalized learning v3 — challenged, and what survived

| v2 element | Challenge result |
|---|---|
| Quiz bandit (Thompson, target-zone reward) | **Survives unchanged.** Upgrade: item bank now grows automatically from videos/web-saves; item metadata gains `source_resource` so the Coach can practice "this week's video." |
| Review scheduler (sim-trained MDP) | **Survives unchanged.** The simulator population and pre-registered baselines (SM-2, FSRS-default, fixed, random) stand. |
| Knowledge-state representation | **Decision forced:** v2 said "Elo or BKT." V3 commits to **Elo-style per-concept ratings** — fewer parameters, robust with sparse data, trivially inspectable, and it keys directly on Concept Graph nodes. BKT is named as the comparison in Future Work, not built. |
| Coach's "prerequisite-readiness" heuristic | **Upgraded from hand-wave to well-founded:** readiness(c) = f(mastery of `prerequisite_of` predecessors in the graph). Still greedy, still honestly labeled non-RL — but now it has the data structure it was pretending to have. |
| Curriculum-RL (rejected in v2) | **Re-examined because the graph now exists — still rejected.** The graph fixes the *state space*; it does not fix single-user sample complexity or semester-scale delayed reward. The honest greedy Coach + the two real RL policies remain the right scope. |

Net effect of V3 on RL: the graph and the video module make the *existing* policies richer (more items, better structure) without adding a third policy. That is the "important part of the platform, not an extra feature" property — RL consumes the whole platform's state rather than living in a corner.

---

## 8. Agents vs tools — the taxonomy, made explicit

Your question "if tools are better than agents for some tasks, explain why" has a rubric answer. **Agent** = owns per-turn decision-making under a prompt+schema+policy, or controls persistent state. **Tool** = deterministic capability invoked *by* an agent or pipeline; no dialogue-turn autonomy. **Stage** = fixed pipeline step with a decision policy.

| Component | Class | Why not the other thing |
|---|---|---|
| Learning / Summarization / Quiz / Flashcard / Coach | **Agents** (5) | Distinct prompts, output schemas, retrieval policies; Coach controls Student-Model policies. |
| Router | Stage (policy cascade) | Classification, not conversation; an "agent" label would re-import the LLM-first cost v2 removed. |
| Verifier | Stage with decision policy | Runs on every answer; its autonomy is a threshold table, not a dialogue. |
| Web search | **Tool** under the Evidence Acquisition Policy | Making it an agent adds an LLM hop to decide what a calibrated gate already decides. |
| Video ingestion | **Tool/adapter** (ETL) | Zero per-turn decisions; it's a pipeline with a progress bar. |
| Graph builder | Offline **pipeline** | Runs at ingestion time, not query time. |
| Transcriber, BM25, dense retriever, NLI checker | Tools | Capabilities, not deciders. |

Final roster is therefore **unchanged in count from v2** (5 agents + router + verifier) despite three major new capabilities — the strongest evidence that V3 added power without adding architectural sprawl. Say exactly that in the defense.

LangGraph wiring *(delta)*: the Learning agent's evidence node now calls the Evidence Acquisition Policy (§5) instead of the bare retriever; a `WEB_OFFER` interrupt returns control to the UI for consent; structural-query intent routes to the graph-native answerer inside the Learning agent.

---

## 9. Memory & Student Model *(delta on v2 §10)*

Working memory, query condensation, and the history-never-replaces-retrieval rule: unchanged. Student Model additions: `concepts` table now foreign-keys the Concept Graph nodes (one ontology everywhere); `items.source_resource` and `interactions.evidence_source ∈ {kb, web, mixed}` added; `web_consents` log. The Study Map reads mastery + graph in one join — the two structures were designed to meet.

---

## 10. Verifier v3 *(delta on v2 §9)*

Three additions, no redesign: (1) **typed evidence** — V2 entailment runs per-claim against the claim's *own cited source* (KB parent or web chunk), so a KB claim can't launder through web text and vice versa; (2) **contradiction across sources** — when KB and web evidence conflict on the same claim, the decision policy forces the surface-the-disagreement output (§5.4) instead of pass/annotate; (3) **video/ASR caveat propagation** — claims resting solely on low-confidence ASR segments get the same ⚠ treatment as low-confidence OCR. Seeded-fault evaluation (E3) gains web-sourced and video-sourced mutants.

---

## 11. UI modules

**Chat** (citations typed KB/Web/Video; hedge banners; web-consent button) · **Library** (documents, videos, saved pages; ingestion progress; per-resource "generate quiz/cards" shortcuts) · **Study Map** (Concept Graph + mastery overlay; click a node → its evidence, its practice items, its videos) · **Practice** (bandit-driven session runner; due cards; per-topic stats) · **Progress** (mastery over time, verifier stats, coverage vs syllabus) · **Settings** (hardware tier, web mode off/ask/auto, language override, model picker).

Streamlit remains — multipage apps cover this. Named risk: the Study Map's interactive graph is Streamlit's weakest fit (st.graphviz or streamlit-agraph are adequate, not beautiful); if it underwhelms, that is a component-level swap, not an architecture change.

---

## 12. Evaluation v3 — E1–E7 unchanged, three additions

| # | What | Set | Metrics |
|---|---|---|---|
| E8 | Concept Graph | 15 multi-hop + 5 structural questions; **50-edge human audit** | multi-hop recall@5 (graph arm on vs off — the ablation that justifies R1), structural-answer correctness, **edge precision** from the audit, graph-build time |
| E9 | Web-fallback decisions | 30 queries: 10 answerable-from-KB, 10 out-of-KB, 10 temporal | decision accuracy (answered locally when it should / offered web when it should), web-answer faithfulness on 10 sampled, conflict-surfacing correctness |
| E10 | Video module | 3 lectures (captioned, uncaptioned, Arabic) | ASR spot-WER on 5-min samples (caption vs whisper), summary faithfulness via Verifier, timestamp-citation accuracy (±10 s), ingestion time per tier |

All sets frozen before Phase-1 coding, joining E1–E7. The E8 graph-arm ablation is the single number that decides whether Graph RAG stays in the final report as a contribution or moves to lessons-learned — we commit to publishing it either way. *That* is the anti-buzzword insurance.

---

## 13. Build phases v3 and the pre-agreed cut list

### 13.1 Phases

**P1 — Spine + bench.** Ingestion (docs only), retrieval core (dense+BM25+RRF, parent expansion, gate), Learning agent, measured-latency harness. *Exit: E1 ablations, E7 measured.*
**P2 — Agents, Router, Verifier, bilingual.** *Exit: E2, E3, E4, E5.*
**P3 — Concept Graph.** G1+G2, graph arm in fusion, structural answers, Study Map v1. *Exit: E8.*
**P4 — Video adapter.** Caption path first, whisper fallback second. *Exit: E10.*
**P5 — Student Model + RL.** Elo, bandit, scheduler-in-sim, Coach, Practice UI. *Exit: E6 sim curves; pilot starts.*
**P6 — Web fallback.** Gate integration, consent UX, tiering, conflict policy. *Exit: E9.*
**P7 — Evaluation campaign + writeup + defense deck.**

Ordering rationale: the graph precedes video (video's concept mining reuses G1/G2); web goes late because it is the most severable feature; RL precedes web because E6's pilot needs calendar time to run.

### 13.2 The cut list (agreed now, executed without meetings later)

If the schedule slips, features are cut **in this order, and only in this order**:
1. Retrieval self-tuning bandit (already optional) → Future Work.
2. Teaching-style bandit (already optional) → Future Work.
3. Web **auto** mode → keep the manual button only.
4. Cross-encoder reranker → off everywhere, reported as ablation-not-shipped.
5. Graph as a *retrieval arm* → keep the graph for Coach + Study Map only (its cheapest two consumers), report E8 as negative/neutral result honestly.
6. Whisper ASR fallback → captioned videos only.
7. Web fallback entirely → refusal + "nearest covered topics" (v2 behavior).

The spine (never cut): ingestion, dense+BM25 retrieval, Learning/Quiz/Flashcard, Verifier V0–V1, quiz bandit, Student Model, E1/E3/E5/E6/E7.

---

## 14. Defense playbook — V3 additions (v2's 15 still apply)

16. **"Why not Neo4j / a real graph database?"** Neo4j is a server; our constraint is in-process, zero-infra local deployment — the same reasoning that chose ChromaDB. At 600 nodes, NetworkX over SQLite is the honest tool; Kùzu is the named growth path.
17. **"Why not full GraphRAG?"** Cost math: per-chunk extraction + gleanings + community summaries ≈ 8–12× our G2 cost on a 7B local model whose extraction quality is the weak link — for a benefit (corpus-global questions) our Summarizer already mostly covers. We kept the 20 % of GraphRAG that serves education: typed concept relations with provenance.
18. **"Can a 7B model extract relations reliably?"** We don't assume it: concepts pass a human curation gate, every edge carries provenance and confidence, singleton low-confidence edges are dropped, and E8's 50-edge audit publishes measured edge precision.
19. **"Doesn't web search break your privacy story?"** Local by default, web by consent: the query leaves the device only when the student presses a button that says so, auto mode is opt-in, and every web call is logged. The claim becomes sharper, not weaker: *nothing leaves without explicit consent.*
20. **"Why is the video summarizer not an agent?"** It makes no per-turn decisions — it's ETL onto the same spine as PDFs. The proof of the design is that quiz/flashcard/graph support for videos required zero new generation code.
21. **"What if YouTube captions are wrong?"** Transcript source is tracked per parent (human/auto/whisper) and surfaced in citations like OCR confidence; E10 spot-checks WER; low-confidence segments get verifier caveats.
22. **"This is very large for a course project."** Seven phases, a frozen evaluation per phase, and a pre-agreed seven-step cut list — scope is managed as an engineering artifact, not by optimism. (Then show §13.2. Reviewers rarely have a follow-up to a cut list.)
23. **"Which single component matters most?"** The Resource Fabric — one ingestion spine is why three new capabilities added zero new agents.

---

## 15. Freeze checklist V3 (supersedes v2 §15; F1–F11 remain frozen)

- [ ] G1. Resource Fabric: one spine, adapters for docs / video / web-save; `persistence` flag semantics (§3)
- [ ] G2. Concept Graph scoped per §4.2–4.3; SQLite+NetworkX; Neo4j rejected; Kùzu = growth path
- [ ] G3. Graph as third RRF arm + native structural answers; BM25 retained; E8 ablation decides its final framing
- [ ] G4. Evidence Acquisition Policy with three-zone gate; web = tool, not agent (§5)
- [ ] G5. Privacy stance: local by default, web by consent; auto mode opt-in; consents logged
- [ ] G6. Web backend: ddgs default behind a swappable interface; source tiering; trafilatura extraction; session-transient with Add-to-KB
- [ ] G7. Video adapter: captions-first, whisper fallback per tier; timestamped citations; overview-note resource
- [ ] G8. RL: Elo committed; bandit + scheduler unchanged; curriculum-RL stays rejected (graph notwithstanding)
- [ ] G9. Agent/tool taxonomy per §8 — agent count unchanged at five
- [ ] G10. Verifier deltas: typed-evidence entailment, cross-source contradiction surfacing, ASR caveats
- [ ] G11. E8–E10 authored and frozen with E1–E7 before Phase-1 coding
- [ ] G12. Phase order P1–P7 and the §13.2 cut list adopted as-is
- [ ] G13. Pending inputs acknowledged: correct summarizer repo link; updated proposal document

*— End of Architecture V3 —*
