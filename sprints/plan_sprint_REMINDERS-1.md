# Sprint REMINDERS-1 — reminders/agenda storage core (Cairn #27, GAP-4 foundation)

> Created 2026-06-21 by architect. LANE 2 (parallel to wiki #25 — different module, zero shared tree). The STORAGE GATE: #28(MCP)/#29(notify)/#30(brief)/#31(fe) all blockedBy #27 → land the schema FIRST so they fan out. User CHỐT'd the alarm/báo-thức model (NOT cairn). Lightweight kickoff (self-contained module-add, scope pre-specified by admin-lead).

## Objective
GAP-4 (dogfood-R4): no task/todo/agenda concept — can't answer "what's on my plate this week." User decomposed #16 → #27-31; #27 = the storage core (a new `modules/reminders/` via the registry pattern). Single-user alarm model: a reminder has a due time, optional repeat, re-notify cadence, and a done-tick.

## Architecture (the locked module/registry pattern)
- New `modules/reminders/` = `router.py · service.py · reader.py · schema.py · store.py · __init__.py` (mirror `modules/news/`). `MODULE = BaseModule(name="reminders", router=router)` (no routines in #27 — the notify routine is #29). Registry AUTO-discovers it (NEVER edit core/main.py to wire).
- **Store: a module-local `modules/reminders/store.py`** with its own SQLite `reminders` table (reminders is relational CRUD + filters + a tick lifecycle → SQLite, not md; mirrors how news/macro own their store.py). Use the central `store/db.get_conn()` connection (one DB file) but the table-init + CRUD live in the module's store.py. (Don't add it to core db.py SCHEMA — keep it module-scoped per the registry principle; init the table on first use like the module stores do.)

## Schema (FREEZE — announce once landed so #28/#31 mirror)
`reminders` table + the `Reminder` pydantic model — FINAL field list (every field, type, default):
| field | type | default | note |
|---|---|---|---|
| `id` | int (PK autoincrement) | — | the reminder id |
| `title` | str (min_length 1, max_length 200, whitespace-stripped) | required | what to do |
| `note` | str \| None (max_length 2000) | None | optional detail |
| `due_at` | str (ISO-8601 datetime) | required | when it's due |
| `repeat` | Literal["once","daily","weekly"] | "once" | recurrence |
| `re_notify_every` | int \| None (minutes, ≥1) | None | re-nudge cadence (for #29) |
| `max_times` | int \| None (≥1) | None | cap on re-notifies (for #29) |
| `notified_count` | int (≥0) | 0 | how many times notified (for #29) |
| `done_at` | str \| None (ISO-8601) | None | set when ticked done |
| `created` | str (ISO-8601) | now | creation ts |

Schema-freeze gate (memory `schema-freeze-gate`): backend FREEZES this field list + ANNOUNCES once landed → THEN #28 (MCP)/#31 (FE) mirror. No moving schema.

## Logic/Algorithm (the non-CRUD bits)
- **tick(id) → done:** set `done_at = now` (ISO). **IDEMPOTENT** — ticking an already-done reminder is a no-op (done_at unchanged, returns the reminder, NOT an error). A `repeat` reminder's tick behavior in #27 = just set done_at (the repeat-roll-forward is #29's notify concern; #27 stores the field, doesn't roll).
- **list filter (the due-filter boundary — EXACT rules):**
  - `today`: `due_at <= end-of-today (today 23:59:59 local/UTC — pick UTC for consistency, document) AND done_at IS NULL`.
  - `week`: `due_at <= now + 7 days AND done_at IS NULL`.
  - `undone`: `done_at IS NULL` (all not-done).
  - no filter / `all`: everything (done + undone), newest-due first.
  - Boundary: `<=` (inclusive of the boundary instant). Document the tz choice (UTC).
- **reader fail-open:** a malformed stored row → skip it + warn, never crash the list (per the reader-returns-shape principle).

## REST (the locked envelope {success, data, warning?})
- `POST /reminders` (create) → 201, the created Reminder (with id).
- `GET /reminders?filter=today|week|undone|all` (list) → the filtered list + stats (count, undoneCount).
- `GET /reminders/{id}` (get) → the reminder, 404 if not found.
- `PUT /reminders/{id}/tick` (tick done) → the ticked reminder (idempotent).
- `DELETE /reminders/{id}` → 204, 404 if not found.
- Error codes: 400 bad input / 404 not found / 422 validation. No auth (single-user).

## Tasks
- **T1 (backend, gating):** the `modules/reminders/` module (router/service/reader/schema/store) + the SQLite table + CRUD + tick(idempotent) + the due-filter + REST + pytest. FREEZE + announce the schema. `docker compose restart backend` (new module → registry discovers on boot; restart to be safe). Backend writes pytest.
- **T2 (tester):** REST round-trip (create→due→stored; tick→done_at set; list today/week/undone boundaries; delete) + the defensive cases (below) + module auto-discovered (in /health modules list). Live on container.
- **T3 (architect):** review + commit (LANE 2, serial w.r.t. lane 1).

## Defensive cases (MANDATORY — handle + test)
- empty list (no reminders) → [] + count 0, not a crash.
- tick an ALREADY-ticked reminder → idempotent (done_at unchanged, no error).
- bad `due_at` (unparseable) → 422 (create-time validation), not a stored bad row.
- delete a non-existent id → 404 (not a 500).
- get a non-existent id → 404.
- title empty/whitespace-only → 422 (min_length + whitespace-strip validator).
- filter with an unknown value → treat as `all` (lenient) OR 422 — pick + document (I lean lenient→all, like activity's lenient filter).

## HARD GATE (distinguishing)
- create + due → stored + GET returns it; tick → done_at set (non-null) + list `undone` EXCLUDES it; list `today` includes a due-today-undone, EXCLUDES a due-today-DONE (the distinguishing: filter respects BOTH due AND done) + EXCLUDES a due-next-week.
- tick-already-ticked idempotent (done_at unchanged).
- module auto-discovered (/health modules has "reminders") — NOT a manual core/main.py edit.
- response envelope {success, data, warning?}; error codes 400/404/422.
- pytest green, mypy clean.

## Baseline
pytest (current ~1707+ — re-anchor at dispatch; lane 1 may move it). Keep 0-failed; expect +CRUD/tick/filter tests.

## Assumptions (user-review)
- **reminders = SQLite (module-local store.py), alarm model** (due_at + repeat + re-notify fields + done-tick). Single-user, no-auth. **How to change:** the schema in modules/reminders/store.py + schema.py.
- **due-filter boundaries:** today = due_at ≤ end-of-today UTC & undone; week = ≤ now+7d & undone; undone = done_at null. `<=` inclusive, UTC. **How to change:** the filter in reader/service.
- **tick is idempotent** (re-tick = no-op, not error); repeat-roll-forward deferred to #29 (notify). **How to change:** the tick in service.
- **unknown filter → lenient `all`** (like activity). **How to change:** the filter parse.

## Notes
- LANE 2 parallel to wiki #25 (different module, zero shared tree). Commits SERIAL w.r.t. lane 1 (1 committer/tree/turn) — whichever lands first commits first, the other rebases. Separate commits (`feat(sprint-REMINDERS-1)`).
- The STORAGE GATE — freeze + announce the schema so #28(MCP)/#31(FE) mirror. #29(notify routine)/#30(brief) build on it too.
- Registry auto-wires the module — NEVER edit core/main.py.
