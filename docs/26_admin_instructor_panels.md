# 26 — Admin & Instructor Panels

Role-gated control surfaces layered on top of the existing platform. Like every other
part of the backend, these are **thin routers** — they aggregate data from stores that
already exist (the web DB, the Student Model, the knowledge catalog, the concept graph,
LLM health) and re-implement no business logic.

## Roles & access control

Access is enforced by the existing `require_role(*roles)` dependency
(`backend/app/deps/auth.py`), which resolves `get_current_user` from the JWT and checks
`User.role` against the allowed set. Three roles exist: `student` · `instructor` · `admin`.

- **Admin** endpoints require `admin`.
- **Instructor** endpoints require `instructor` **or** `admin`.

The role dependency is declared as the **first** parameter on the service-using endpoints,
so an unauthorized request is rejected (401/403) **before** the heavy shared `AlaServices`
singleton is constructed — no wasted work, and the gate is unit-testable without the corpus.

In the frontend, the sidebar shows the **Instructor** / **Admin** entries only to those
roles; a student's sidebar is unchanged. Each page also guards on `user.role` for a clean
message, and the server remains the source of truth (returns 403 regardless of the UI).

## Admin API (`/api/admin`, role: admin)

| Method | Path | Purpose | Reuses |
| --- | --- | --- | --- |
| GET | `/admin/users` | List all users | web DB (`User`) |
| PATCH | `/admin/users/{id}` | Change a user's role (`{role}`) | web DB |
| DELETE | `/admin/users/{id}` | Delete a user (chats cascade) | web DB |
| GET | `/admin/stats` | Users by role, chat/message/upload counts, catalog size, graph stats | web DB + `catalog.list_all` + `graph.statistics` |
| GET | `/admin/health` | LLM reachability, catalog, graph, vector-store location | `ala.llm.factory.available_provider` + catalog + graph |

**Safety guards:** the last remaining admin cannot be demoted or deleted (avoids lockout),
and an admin cannot delete their own account. Invalid roles are rejected (422).

## Instructor API (`/api/instructor`, role: instructor|admin)

| Method | Path | Purpose | Reuses |
| --- | --- | --- | --- |
| GET | `/instructor/students` | Cohort roster with mastery summary per student | `User` (role=student) + `student_model.mastery_summary` |
| GET | `/instructor/student/{student_id}` | One student's weak/strong concepts + summary | `student_model.weak_concepts` / `strong_concepts` |
| GET | `/instructor/overview` | Cohort aggregates: active count, average mastery, mastery distribution, most common weak concepts, content inventory | Student Model + catalog |
| GET | `/instructor/content` | Content inventory by type and course | `catalog.list_all` → `ResourceMetadata` |

The cohort is the set of **registered** students in the web DB. Their mastery is read from
the existing Student Model with **read-only** calls (`mastery_summary`, `weak_concepts`,
`strong_concepts`) — these return empty results for a student who has not studied yet and
never write, so listing the cohort has no side effects. All cross-student figures
(averages, distribution buckets, weak-concept frequencies) are plain aggregation of those
existing summaries — no new learner logic.

## Frontend

- `frontend/src/app/(app)/admin/page.tsx` — stat cards, a users table with an inline role
  selector and delete action, users-by-role, and a component-health card.
- `frontend/src/app/(app)/instructor/page.tsx` — cohort stat cards, mastery-distribution
  bars, most-common-weak-concepts, content inventory, and a students table; clicking a
  student expands their weak/strong concept detail.
- API wrappers: `adminApi` / `instructorApi` in `frontend/src/lib/client.ts`.

## Tests

`backend/tests/test_api.py` adds `test_admin_panel_role_gate` and
`test_instructor_panel_role_gate` — each asserts 401 for anonymous requests and 403 for a
student, on SQLite alone (no ala corpus needed, because the role gate short-circuits first).
The full ala platform suite (232 tests) remains green — this milestone added only files
under `backend/` and `frontend/` and changed no `src/ala/` code.
