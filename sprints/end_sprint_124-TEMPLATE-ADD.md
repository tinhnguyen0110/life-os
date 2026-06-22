# end_sprint_124-TEMPLATE-ADD — re-add template→activity add-button (as a BINARY TODO) (Cairn #124, TRACING-UX2 T3)

> Result. The user's OWN saved todo-list (the #109 template store, intact but its import dropped in #121) is re-usable as a 1-click "add → today's activity". Added POST /tracing/templates/{id}/add + /add-all, mapping a template → a BINARY TODO (goal=1, name-only — the #122 text+tick model), NOT the stored goal. Commit `<hash>` `fix(sprint-124-template-add)`. Status: ✅ verified (backend-w3 built + the goal=1 correction applied; architect 4-step + INDEPENDENT live tick→done proof). Cairn #124 TRACING-UX2 T3 — be-only, CLOSES on this commit. Disjoint from #123 (FE, parallel). #125 unblocks (serial, after this).

## What shipped
| File | Change |
|---|---|
| `tracing/service.py` (`_template_to_activity_input` + add/add-all) | import = `ActivityInput(id=t.id, name=t.name, goal=1.0)` — name-only + goal=1; the template's stored goal/unit/emoji/color DROPPED. add (single, idempotent skip-already-added) + add-all (non-hidden, {created,skipped}). |
| `tracing/router.py` | POST /tracing/templates/{id}/add ({activity,added}) + POST /tracing/templates/add-all ({created,skipped}); 404 unknown id; honest-empty add-all. |
| `tests/test_tracing_template_add.py` (NEW, 13) | 🔴 import→goal=1-name-only (stored goal=20→goal=1, unit/emoji dropped) + stored-goal=8→goal=1 + **tickable: import stored-goal=20 template → tick → done=True** + idempotent skip + 404 + honest-empty + add-all. |

## Design (LOCKED — template = a saved TODO TEXT, import = binary todo goal=1)
- **🔴 import → goal=1 (binary todo), name-only.** The #122 redesign made /tracing text+tick (todo = goal=1, tick=done via `done=val≥goal`). A #109 template has a stored goal (seed goal=8/20/30). Importing WITH that goal → a measured progress-bar habit on the checkbox screen → an UN-TICKABLE todo (tick once → val=1<goal → done stays false). So import maps template.name → goal=1, DROPS the stored goal/unit/emoji. "Template" now = a saved todo TEXT, not a measured-habit preset. (The decide-and-log evolution: my dispatch first said "preserve the goal" — team-lead overrode it [Rule#0, verified the un-tickable bug]; the flag-before-commit caught it uncommitted.)
- the #109 store keeps its goal/unit/emoji columns (backward-compat unchanged) — ONLY the #124 import path ignores them.
- explicit user-action (click "+ Từ mẫu") on the user's OWN saved list — NOT the rejected hard-code-chip auto-seed. add = idempotent (skip already-added-today, no dup); add-all = all non-hidden, {created,skipped}.

## Verification (Rule#0 — architect INDEPENDENT, the corrected distinguishing case)
- **architect 4-step (read FULL):** `_template_to_activity_input` = goal=1 name-only (verified the mapping); the add/add-all + idempotent skip + 404. Staged #124 BE-only (the 6 #123 FE files left dirty — disjoint parallel). ✅
- **🔴 INDEPENDENT LIVE proof (the un-tickable-bug surface, behavior-test not field-read):** imported `uong-nuoc` (stored **goal=8**) → the created activity has **goal=1.0** (not 8); **ticked once (val=1) → today.done = True** (val=1 ≥ goal=1) — the EXACT bug the override fixes (preserve-goal would've left done=False, un-tickable). name "Uống nước" preserved; stored shape dropped. Scoped-cleaned the probe (#72). ✅
- **the test asserts the BEHAVIOR:** test_imported_stored_goal20_template_is_tickable (tick→done) + goal==1 assertions — not just persistence. ✅
- **mypy --no-incremental** clean; **26 passed** (template-add + tracing, independent); backend FORWARD 2399/0 == REVERSE; 13 #124 tests. ✅

## 3 Gates
- **Gate 1 (API):** POST /add ({activity,added}) + /add-all ({created,skipped}); 404 unknown; honest-empty; idempotent skip — agent-readable. ✅
- **Gate 2 (Function):** import→goal=1 + the tick→done behavior test + idempotent + 404 + honest-empty + 26 passed + mypy clean. NOT self-confirming (the tick→done is the consumer-behavior proof). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live tick→done; staged EXACTLY #124 BE (NO #123 FE / template / data leak — the 6 FE files left dirty); commit format. ✅

## Assumptions (user-review)
- **template import → goal=1 binary todo (name-only); stored goal/unit/emoji IGNORED** — the #122 text+tick model. **How to change:** the import mapping `_template_to_activity_input` (re-add the stored goal if /tracing ever returns to measured-habits).
- **add = idempotent (skip already-added-today)**; add-all = all non-hidden. **How to change:** the add/add-all skip logic.

## Notes
- Cairn #124 TRACING-UX2 T3 — user-CHỐT (re-usable saved-todo list, 1-click add). backend-w3 built; the goal=1 correction applied cleanly (it wasn't mid-build — a targeted flip); architect committed (§3 sole-committer). 🔴 **The decide-and-log evolution is the lesson** (recorded `decide-and-log-check-downstream-consumer-contract`): my "preserve the template's stored goal" was locally reasonable but contradicted the recently-redesigned #122 consumer (done=val≥goal → a stored goal>1 is un-tickable). team-lead overrode it (Rule#0, read the render) + the flag-before-commit caught it uncommitted → the right value (goal=1) is dictated by the RENDER contract, not the source shape. The 4-step verified the CONSUMER behavior (tick→done=True) not just the goal field — the proof that matters. **Parallel-lane staging (7th clean):** committed BE-only while #123 FE in flight (6 files left dirty, leak-check clean). **#125 (note one-shot future-date remind) now unblocks** (serial, same tracing — I dispatch it next). REST-only, no restart, no count-assert.
