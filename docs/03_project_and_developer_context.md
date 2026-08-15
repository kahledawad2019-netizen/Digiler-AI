# Milestone 2 — Project Context + Developer Context (Tasks 5 & 6)

**Status:** implemented & tested (**48 passing tests**). Architecture baseline: **V3**.

Two complementary "self-knowledge" artifacts: one **machine-readable** (for
agents/automation), one **human-readable** (for AI coding assistants & engineers).

---

## Task 5 — Project Context (machine-readable)

### What it is
A live, structured description of everything the platform knows about itself:
build/schema versions, configuration (embedding model, LLM, vector store,
retrieval strategy), every component with its status, the courses, and the live
knowledge-base status. Future agents read this **before acting**.

### How it's built (declared ⊕ live)
```
platform.yaml            ─┐  build/schema versions
context.declared.yaml    ─┼─▶ ProjectContextService.build() ─▶ ProjectContext
catalog + taxonomy       ─┘  live KB status + courses
```
- **Declared** ([contexts/context.declared.yaml](../contexts/context.declared.yaml)) — the
  component roster, model choices, and subsystem statuses. Update a status in one
  line as milestones land; no code change.
- **Live** — knowledge-base statistics come straight from the `KnowledgeCatalog`;
  courses come from the taxonomy. So the context is never conceptually stale —
  `build()` always reflects current state.

### Auto-update (the Task 5 requirement)
`ProjectContextService.refresh()` publishes the snapshot to
[contexts/project_context.yaml](../contexts/project_context.yaml). It is wired as the
**Registry's `on_change` hook**, so registering a resource or changing its status
automatically republishes the context. The hook is decoupled (default `None`), so
the registry has no hard dependency on the context subsystem — clean Observer.

### Files & classes
```
src/ala/context/
├── models.py   # ProjectContext, ComponentInfo, ConfigurationInfo,
│               # CourseInfo, KnowledgeBaseStatus, ComponentStatus
└── service.py  # ProjectContextService.build() / refresh() / from_settings()
```

### Use it
```powershell
.\.venv\Scripts\ala.exe context show       # print live context (YAML)
.\.venv\Scripts\ala.exe context refresh     # write contexts/project_context.yaml
```

---

## Task 6 — Developer Context (human/AI-assistant readable)

[contexts/DEVELOPER_CONTEXT.md](../contexts/DEVELOPER_CONTEXT.md) — vision,
architecture summary, tech stack & dependencies, folder structure, design
principles, naming conventions, current progress, remaining milestones,
constraints, and the working agreement. A root
[CLAUDE.md](../CLAUDE.md) points assistants here and is auto-loaded by Claude Code.

**Division of labour:** the *stable* narrative (principles, architecture, rules)
is hand-maintained in the Markdown; the *live* numbers (component statuses, KB
counts) live in `project_context.yaml`. The Markdown links to the YAML rather
than duplicating it, so the two never drift.

---

## Why two files instead of one
- Agents need **structured, queryable** state → YAML/JSON (`project_context.yaml`).
- Humans/coding assistants need **narrative + rationale** → Markdown
  (`DEVELOPER_CONTEXT.md`).
  Forcing either into the other's format serves neither. They cross-reference.

## How to test
```powershell
.\.venv\Scripts\python.exe -m pytest -q      # 48 passed
```
`tests/test_context.py` covers: declared⊕taxonomy merge, KB status reflecting the
catalog, snapshot writing, and the registry `on_change` hook firing.
