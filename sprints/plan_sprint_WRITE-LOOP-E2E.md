# Sprint WRITE-LOOP-E2E — exercise + harden the propose→accept→land agent loop

**Task #51. Theme:** the agent write loop (`propose_*` → human accept → row lands in the target module) has never been exercised end-to-end (agent_proposals queue 0-accepted-ever). Verify it live, lock it with an e2e test, fix the gaps the live run exposes.
**Type:** numbered sprint (single backend theme, ~3-4 tasks).
**Source:** round-3 convergence judgment (the strategic last backlog sprint).

## Kickoff — 2026-06-16 (verified LIVE in-process — the loop is NOT a stub, but has 2 real bugs)

### The loop EXISTS and is WIRED (not a stub)
- `mcp_servers/proposals_service.py:accept()` is fully built: atomic PENDING→ACCEPTED (mark_decided) → apply-exactly-once via `APPLY_HANDLERS` → records `applied_ref` / `apply_error`, idempotent, audited, fail-soft.
- REST surface exists: `modules/agent_proposals/router.py` → `POST /agent-proposals/{id}/accept` + `/reject` (idempotent, no auth). **Natural-call shape is SAFE**: `accept_agent_proposal(proposal_id, decided_by="user")` takes the id + a string, NOT a create-schema body → no 422-on-partial-call risk (the W7-A2 concern does NOT apply here).
- `APPLY_HANDLERS` = `{decision_create, note_create, journal_create}`.

### LIVE e2e run (in-process, isolated tmp) — what actually happens
- ✅ **decision_create:** propose_decision → accept → **LANDS** in decision_journal (applied_ref set, count 0→1, entry findable). WORKS.
- ✅ **note_create:** propose_note → accept → **LANDS** in notes (applied_ref set). WORKS.
- ✅ **reject:** propose → reject → status=rejected, appliedRef=None, nothing applied. WORKS.
- 🔴 **journal_create — BROKEN (the real bug):** `propose_journal("buy"/"sell", ...)` stores `action` LOWERCASE, but `_apply_journal_create` passes it raw to `JournalInput(action=...)` where `Action = Literal["BUY","SELL"]` (uppercase only, no normalization). → accept RAISES a pydantic validation error → `applied_ref=None`, **NOTHING lands.** The journal write loop is dead end-to-end. (Decision/note work because their payloads match the target schema; journal doesn't.)
- 🟠 **project_update — UNHANDLED (known gap):** no handler in APPLY_HANDLERS → accept records `apply_error="no apply handler for kind 'project_update'"`, no row. So `write_server.propose_project_update` is a dead-end (accepts but never applies). The agent can propose a project update that can never land.

### Verdict — this is fix-the-gap, not just add-a-test (the live run earned its keep)
The loop is real for decision/note but the live run exposed 2 genuine defects (journal case-mismatch + project_update unhandled). The sprint = (1) FIX journal apply, (2) DECIDE project_update (handle it or honestly reject-at-propose), (3) the e2e TEST that locks ALL of it in so the loop can't silently rot again.

### Final task list (proposed — pending team-lead approval)
- **T1 (bug fix):** `_apply_journal_create` normalizes `action` to uppercase (`str(payload["action"]).upper()`) before `JournalInput` — defensive, fixes already-queued + future proposals regardless of the case the agent sends. (Optionally also tighten `propose_journal`'s docstring to say it normalizes.) After: propose_journal→accept→LANDS in journal.
- **T2 (project_update decision — team-lead's call):**
  - (a) **Add an apply handler** `_apply_project_update` → `modules/projects.service` update of the human-authored fields (progress/next/desc) the proposal carries. Closes the loop. (Verify projects.service HAS such an update fn first — if not, this is bigger.)
  - (b) **Reject at propose-time** — if project_update can't cleanly apply, make `propose_project_update` honest (don't offer a write that can't land), OR keep it accepting-with-apply_error but document it. I LEAN (a) if projects has an update fn; flag to team-lead.
- **T3 (e2e test — the lock):** `test_write_loop_e2e.py` — for EACH applicable kind (decision/note/journal[+project if T2a]): propose via write_server → accept via the REAL path → **re-GET the target module and assert the row LANDED with correct fields** (behavior-test the side effect, not the helper). + reject leaves it unapplied. + the natural-call shape over the REST router (id + decided_by, partial). + idempotent double-accept doesn't double-apply. Use DIVERGENT field values so a collapsed/wrong apply differs from a correct one.
- **NG5 (bundle ONLY if cheap):** stale `/tinhdev/...` repo path → 5 stderr warnings/call. Different area (projects status.md config) — likely SEPARATE; leave unless trivially co-located.

### Locks (team-lead, 2026-06-16 — after kickoff approval; both findings disk-confirmed)
- **T1 — FIX journal (the deliverable).** `_apply_journal_create` normalizes `action=str(payload["action"]).upper()` before JournalInput. Bug-killer test = propose LOWERCASE "buy" → accept → re-GET journal → action=="BUY". Don't change the Action Literal/schema — normalize at the apply boundary.
- **T2 = (b) honest-defer project_update, PINNED.** team-lead confirmed it's a DELIBERATE documented non-handler (proposals_service:28-32), NOT a bug. Do NOT build update_project (over-engineering, no consumer demand — north-star). Test PINS it: accept → apply_error set + 0 projects rows + proposal recorded (so the defer can't silently drift into a fabricated write).
- **T3 — full e2e lock.** test_write_loop_e2e.py: LANDS (decision/note/journal-fixed, re-GET the module + DIVERGENT fields) + project_update honest-apply_error + reject-unapplied + idempotent-double-accept (count stable) + natural REST-call (id+decided_by, no 422). behavior-test the side effect, not the helper.
- **NG5 — LEAVE** (separate area, projects status.md config). Not this sprint.

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done → team-lead live-verifies (propose lowercase journal → accept → re-GET shows BUY landed) → architect review+commit+push. **This is the LAST backlog sprint — after it ships, clean checkpoint.**
