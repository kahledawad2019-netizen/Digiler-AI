# CLAUDE.md — ALA (AI Learning Platform)

AI coding assistants: **start with [`contexts/DEVELOPER_CONTEXT.md`](contexts/DEVELOPER_CONTEXT.md)**
(vision, architecture, standards, folder map, constraints) and the live state in
[`contexts/project_context.yaml`](contexts/project_context.yaml).

## Fast facts
- **Architecture baseline:** V3, **frozen** ([`ALA_Architecture_v3.md`](ALA_Architecture_v3.md)). Incremental changes only; don't redesign.
- **Metadata schema:** v2.0.0, **frozen** (`src/ala/metadata/schema.py`).
- **Python:** use `py -3` (no bare `python` on PATH). Venv: `.venv`. Deps: pydantic + pyyaml only (plus stdlib sqlite/hashlib).
- **Package:** `src/ala/` (core · config · metadata · catalog · registry · fabric · context · cli).

## Commands
```powershell
.\.venv\Scripts\python.exe -m pytest -q      # run tests
.\.venv\Scripts\ala.exe context show         # platform self-description
.\.venv\Scripts\ala.exe init                 # create catalog + KB folders
```

## Rules (non-negotiable)
- **Do NOT touch `KNOWLEDGE BASE/`** — original corpus, read-only until migration is approved.
- Raw is immutable; write only to `knowledge_base/derived/`. Reference `resource_id`, never paths.
- Config over hardcode. Clean Architecture + SOLID. Every module ships docs + tests.
- Build in milestones; explain and **wait for approval** before the next stage. Commit only when asked.
