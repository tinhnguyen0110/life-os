# Sprint WIKI-AIFIRST — bỏ chế độ duyệt, AI-first ghi thẳng tri thức

Board task: #168. User CHỐT 2026-06-29: "bỏ chế độ duyệt, AI-first ghi thẳng tri thức, đã có CRUD thẳng folder, bỏ inbox."

3 locked user decisions:
1. **Inbox** → BỎ HẲN màn `/wiki/inbox`. Refine làm trong `/wiki/[id]`.
2. **Proposals** → GIỮ màn, đổi thành **AUDIT-LOG** (xem AI ghi gì + lùi/reverse), bỏ vai cổng-duyệt.
3. **wikiAgentAutonomous** → default ON.

## Kickoff — 2026-06-29

### Drift since plan was written (significant — premise stale)
- **BE flip-default = NO-OP, already done.** `modules/settings/schema.py:44` already has `wikiAgentAutonomous: bool = Field(default=True, ...)` and LIVE config reads `True`. `_autonomous_enabled()` (proposals_service L116) just reads `get_config().wikiAgentAutonomous`. The dispatch premise "hiện default OFF" is stale. **No BE flip needed.**
- **REST auto-apply defense intact** — only MCP `write_server.py` passes `auto_apply_eligible=True` (L144); REST `router.py:536` `create_proposal(body)` never does. F1-S1 trust boundary holds. **No BE work here.**
- **Proposal record kept when autonomous** — auto-accept (proposals_service L101) flips row to `accepted` with `decidedBy="agent:auto"`, never deletes. Audit-log DATA already exists. **No BE work to "keep records".**
- **Reverse path EXISTS (partial, by design):** `service/crud.py` has `soft_delete_note` (L64, recoverable) + `restore_note` (L81); proposal kinds `note_softdelete`/`note_restore` already wired through the chokepoint (proposals_service L201-211). So:
  - `note_create` auto-write → undo = **soft-delete the landed note** (`appliedNoteId`). Fully supported TODAY via existing `DELETE /wiki/notes/{id}` (soft) or MCP.
  - `note_edit` / `link_add` / `link_remove` / `merge` → **no one-step content-revert** (no per-note version store; #95 parked). Undo for these = manual refine on the note. NOT building a version store this sprint (out of scope, over-engineering for 1-user).
  - → Reverse is **PARTIAL by design**: build the create-undo (soft-delete) path in the audit-log; for edit/link/merge, the audit row deep-links to the note so the human refines manually. Document honestly in `## Assumptions`.
- **FE `/wiki/[id]` refine already complete** — edit body, status select (fleeting→developing→evergreen), tags, `[[link]]` via body edit. The ONLY inbox coupling is the back-button → `/wiki/inbox` (L152). Refine-affordance gap vs old inbox = effectively ZERO.

### Plan revisions (drift collapses the BE task)
- **BE**: original 3 sub-tasks (flip default / keep-record / reverse) → only **reverse-path surface** remains, and the core (soft-delete) already exists. BE work shrinks to: confirm autonomous-default via test (assert default=True + auto-apply lands a note) + ensure the audit-log read endpoint returns enough for the FE undo (appliedNoteId, kind, decidedBy, status). Likely **no new BE endpoint** — `GET /wiki/proposals?status=accepted` + existing `DELETE /wiki/notes/{id}` (soft) cover it. BE = a small verify/guard task, not a build.
- **FE**: the real work. Remove inbox route+nav+all links (no 404), reframe proposals → audit-log (default filter `accepted`, demote accept/reject gate, add "lùi" = soft-delete for note_create, deep-link for others), relabel nav, fix `/wiki/[id]` back button.

### Nav label decision (architect chốt)
- `/wiki/proposals` nav label: **"Nhật ký AI"** (screen stays P1; route unchanged so deep-links survive). Crumb: **"Nhật ký AI · audit"**.
- Reason: "Nhật ký AI" = clearest Vietnamese for "what the AI wrote (audit log)"; matches the rest of the VN nav. Keeps route `/wiki/proposals` so no redirect needed.

### Final task list
- **T1 (BE, small)** — autonomous-default + audit-read guard: pytest asserting `wikiAgentAutonomous` default True + MCP propose auto-applies (note in vault + accepted proposal record) + REST propose does NOT auto-apply. Confirm `GET /wiki/proposals?status=accepted` returns `{kind, decidedBy, appliedNoteId, status, created, rationale, targetId}` for the FE undo. No new endpoint expected.
- **T2 (FE, main)** — remove `/wiki/inbox`: delete route dir + test, remove nav item (L92) + crumb (L153), remove all inbox links (api/wiki.ts getWikiInbox keep-or-remove?, types, useWiki, _rows InboxRow, page.tsx inbox column + 3 links → repoint to vault or remove), fix `/wiki/[id]` back button (L152 `/wiki/inbox` → `/wiki`). Guard: no dead link, no 404, existing fleeting notes still reachable via Vault.
- **T3 (FE, main)** — `/wiki/proposals` → audit-log: default filter `accepted`, demote accept/reject-as-gate (keep accept/reject available for any still-pending legacy row but not the headline CTA), add "lùi/reverse" per accepted row (note_create → soft-delete appliedNoteId; note_edit/link/merge → deep-link "mở note để refine"), reframe banner/title to "Nhật ký AI ghi", relabel nav.
- T2 ∥ T3 (both FE, mostly disjoint files: T2=inbox+nav+vault+[id], T3=proposals page+nav label) — coordinate the shared nav.ts edit (T2 removes inbox item, T3 relabels proposals item) → I'll have ONE agent (frontend) do both T2+T3 so nav.ts is edited once, no shared-file race.

### Dispatch plan
- **frontend** ← T2 + T3 together (shared nav.ts → one committer, one agent).
- **backend** ← T1 (verify/guard) in parallel (disjoint: backend tests vs FE app).
- **tester** ← verify after both: vitest 100% (update/remove inbox test, add audit + autonomous-default tests), tsc, pytest wiki layer, API (propose→auto-apply→reverse).
- team-lead Chrome-gate before push.

## Assumptions (user-review) — filled in end_sprint
