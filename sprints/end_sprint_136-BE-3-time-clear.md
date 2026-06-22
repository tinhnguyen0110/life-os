# end_sprint_136-BE-3-time-clear — fix: a set per-activity `time` was un-clearable

> Reactive sprint (B-tier), parent #136. frontend found (Rule#0): the #136 `time` field (fdc23b9) could be SET but not CLEARED — `update_activity` does `model_dump(exclude_none=True)`, which drops `{time:null}` (the FE "Xóa giờ" clear gesture) → never writes → the time stays. Stacked on fdc23b9 (both local/unpushed → push together with #136, no broken intermediate on origin).

## The bug
`exclude_none=True` (service.py:300) can't distinguish "field omitted (leave unchanged)" from "field set to null (clear)". Only `time` is user-clearable (remindAt clears via `remindRepeat="off"`, not null), so the clear gesture silently no-op'd.

## The fix (surgical, behavior-preserving)
In `update_activity`, after the exclude_none dump, special-case `time` via `model_fields_set` (pydantic v2 = the fields the request actually supplied):
```python
if "time" in upd.model_fields_set and upd.time is None:
    fields["sched_time"] = None
```
This clears sched_time ONLY when the caller EXPLICITLY passed `time:null` (in the field-set + value None). A request that OMITS time → not in the set → unchanged. **NOT `exclude_unset` on the whole dump** — that would flip remindAt/remindRepeat/remindChannel's existing "None = unchanged" semantics (a regression). Scoped to `time` only.

## Verify (architect 4-step + live)
- **Live (architect, on :8686):** set time=07:15 → PUT {time:null} → GET → `time=None` (CLEARED) ✓.
- **Control 1 (no sticky-clear):** clear → PUT {time:"08:00"} → `time=08:00` ✓ (re-set works).
- **Control 2 (other-field semantics preserved):** PUT {name:"…"} with remindAt OMITTED on a reminder-activity → `remindAt=09:00` UNCHANGED ✓ (the special-case did NOT over-reach).
- **pytest:** 67 pass / 6 skip / 0 err on the focused set (the +46-line clear-path test in test_tracing_time_field.py). mypy --no-incremental clean.
- **Side-effect cleanup:** the stuck real activity "hoc" (left at time=07:15 by frontend's probe, un-clearable pre-fix) → backend cleared it post-fix → `hoc time=None` ✓.

## Gates
- Gate 1/2 (API/Function): clear-path test asserts behavior, 2 controls (re-set + other-field-unchanged), mypy clean, edge (omit vs explicit-null), no self-confirming assert. ✓
- Gate 3 (Sprint): this doc + spot-checked the full function + the 2 controls live + count ≥ baseline. ✓

## Assumptions (user-review)
- **time clears via explicit `{time:null}`** (the FE "Xóa giờ" gesture), scoped to the `time` field only. Why: time is the one user-clearable field (remindAt has its own clear via remindRepeat=off); a whole-dump exclude_unset would regress the others. How to change: if the user wants a different clear gesture (e.g. empty-string), adjust the special-case condition.

## Commit
- Hash: (filled at commit) — `fix(sprint-136-be-3): a set per-activity time was un-clearable (exclude_none dropped time:null)`
- Files: backend/modules/tracing/service.py + backend/tests/test_tracing_time_field.py + this doc.
- Pushes together with fdc23b9 (#136-BE-2) + 79fe71c (#136-FE) — one atomic push, no broken intermediate on origin.
