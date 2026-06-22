# end_sprint_137-T1-template-sets — template-SETS BE (mẫu = a saved LIST of rich activities)

> Sprint 137 Task T1 (BE). The current "mẫu" = 1-word CHIPS (flat `tracing_template`, one row = one prefill) — the user rejects it ("a chip adds an empty line, saves nothing"). A "mẫu" must be a saved LIST of full activities (a reusable routine) — 1-click imports the WHOLE list, each member preset with time + reminder + channel. This is the BE structural half; #137-T2 (FE modal) builds on the frozen shape. Built on the clean 85aa789 tree (post-#136).

## What shipped (backend/modules/tracing/{schema,store,service,router}.py + tests)
A NEW template-SET surface (separate from the dormant #109 chip table):
- **store.py:** NEW table `tracing_template_set { id TEXT PK, name TEXT, activities TEXT (JSON) }` (CREATE IF NOT EXISTS, no ALTER) + CRUD (list/get/upsert/delete) + `delete_all_template_sets` (🔴 SCOPED to the table — the #72 blanket-delete lesson honored in code + comment).
- **schema.py:** TemplateSet `{id, name, activities: TemplateMember[]}`; TemplateMember `{content, time: str|null (HH:MM), remindRepeat: off|daily|weekdays, remindChannel}`; TemplateSetInput `{name (1-80 non-blank), activities[]}` (member content 1-120 non-blank; bad time/blank → 422 via validators).
- **service.py:** `_slug` (ASCII-folds Vietnamese diacritics → readable ids), fail-soft `_row_to_template_set` (malformed JSON blob → honest-empty + warning), CRUD with slug-id collision avoidance, and 🔴 `import_template_set` — each member → `create_activity(name=content, goal=1.0 BINARY todo, time=member.time, remindAt=member.time IF remindRepeat≠off else None, remindRepeat, remindChannel)`, unique id per member (no 409 re-import), **fail-soft per member** (one bad → skipped, rest import), returns `(created, skipped)`. `reset_template_sets` → SCOPED discard-all + re-seed the default "Buổi sáng".
- **router.py:** 6 routes — static (`/template-sets`, `/template-sets/reset`) declared BEFORE the `/{set_id}` dynamic ones (FastAPI matches static first — a routing-order bug avoided); 404 via `agent_error_response` (agent-readable hints, the #46 REST parity). Registry auto-discovered (NO core/main.py edit).

## Verify (architect 4-step + live)
- **Read full functions:** router (route order + 404 hints), store (SCOPED deletes), service (import→create_activity goal=1 + reminder-at-member-time + the slug-id uniqueness + fail-soft). All correct.
- **Live (architect, on :8686):** create a 2-member set (one timed+reminded, one bare) → GET lists it → POST /import → 2 today-activities: "Uống nước test" goal=1.0, time=07:00, remindAt=07:00 (reminder fires, daily, discord); "Đọc sách test" goal=1.0, time=None, remindAt=None (bare — the independence); skipped=[] (unique ids, no 409) → reset → exactly 1 set "Buổi sáng" (3 members) → SCOPED cleanup of the 2 imported activities (200/200). ✓
- **pytest:** 105 passed / 6 skipped / 0 err (20 new template-set tests + existing tracing). mypy --no-incremental clean (6 files). backend's FORWARD+REVERSE 2501/0.

## Gates
- Gate 1 (API): schema validators (name/content non-blank, time HH:MM), integration tests, response `{success,data}` + `{sets}`/`{created,skipped}`/`{deleted}`, 404 via agent_error_response, no auth (single-user), module auto-discovered. ✓
- Gate 2 (Function): unit tests assert behavior (import goal=1 + presets, reminder-at-member-time, time-no-remind→no-reminder, unique-ids-no-409, SCOPED reset, blank/bad→422), mypy clean, fail-soft import + malformed-blob honest-empty. ✓
- Gate 3 (Sprint): this doc + spot-checked full functions + live round-trip + count ≥ baseline. ✓

## Assumptions (user-review)
- **Model B (JSON activities column)** — a template-set is always read/written/imported WHOLE → a JSON blob is the leanest model (no child table). How to change: a relational child table if per-member queries are ever needed (not now).
- **import id = slug(content) + numeric suffix** avoiding existing ids → re-import never 409s (creates fresh activities). Why: a routine imported twice should add the activities again, not error. How to change: dedup-by-content (skip existing) if the user wants idempotent import.
- **reset default = "Buổi sáng"** (Uống nước@07:00 daily, Tập thể dục@07:30 daily, Đọc sách@08:00 no-reminder). A sensible VN morning routine; the #109 reset pattern extended to sets. How to change: edit `_DEFAULT_TEMPLATE_SET`.
- **The flat #109 chip `tracing_template` is LEFT DORMANT** (not removed) — it's still read by REST GET /tracing/templates + the MCP `tracing_templates` (#24 parity tool) + count-asserts; removing it would break parity/counts. The FE removes only the chip UI ROW (#137-T2). How to change: a deliberate parity-aware removal sprint if the chip surface is ever fully retired.

## Commit
- Hash: (filled at commit) — `feat(sprint-137-t1-template-sets): template-SET store + CRUD + import→today + reset (mẫu = a saved list of rich activities)`
- Files: backend/modules/tracing/{schema,store,service,router}.py + backend/tests/test_tracing_template_set.py + this doc.
- BE-only — FE #137-T2 (the modal) commits separately when complete (serial through architect).
