# Sprint W4a — Proposal/approval-queue backend · END

**Status:** ✅ implemented + verified live (Rule#0) · 1 gap found → W4a-fix dispatched (audit wiring).
**Commit:** (pending — W4a + W4a-fix committed together after audit re-verify)

## What shipped
The trust-boundary foundation for M4 MCP: an AI write can NEVER land in the vault directly — it
becomes a `pending` proposal that a human must `accept`. Verified the pillar holds in code.

### Files (4 new, 2 edited — registry auto-discovered, no core/main.py edit)
- NEW `modules/wiki/proposals_schema.py` — ProposalCreateInput / Proposal / DecideInput / BatchAcceptInput (camelCase contract).
- NEW `modules/wiki/proposals_store.py` — `wiki_proposals` + `wiki_mcp_audit` tables (shared SQLite), CRUD + mark_decided (pending-guard) + append_audit (append-only) + recent_audit.
- NEW `modules/wiki/proposals_service.py` — create (intent only) + apply-on-accept via M1 single-writer + accept/reject/batch_accept + per-kind apply-handlers.
- NEW `tests/test_wiki_proposals.py` — 30 tests.
- EDITED `modules/wiki/router.py` — +6 endpoints (static paths before /{id} so batch-accept isn't captured as an id).
- EDITED `modules/wiki/store.py` — 1-line quick-fix `from typing import Any` (pre-existing latent missing import, surfaced by mypy now traversing store.py).

### Endpoints
POST /wiki/proposals · GET /wiki/proposals?status= (+counts) · GET /wiki/proposals/{id} ·
POST .../{id}/accept · POST .../{id}/reject · POST /wiki/proposals/batch-accept.
Codes: 404 absent · 409 already-decided · 422 invalid payload/mutation. Envelope {success,data,warning?}.

## Verified LIVE on container :8686 (team-lead, Rule#0 — EXERCISED, not field-read)
- pytest 883 passed / 6 skipped / 0 fail (baseline 853 +30) · mypy clean · 30 def == 30 collected (no dup-shadow).
- **CREATE writes NOTHING to vault** (propose note_create → totalNotes unchanged) — the M4 pillar.
- **ACCEPT applies via single-writer + PERSISTS** (note roundtrip: title/content/author reflected) + warning.
- **REJECT applies nothing** · double-accept → 409 · **fail-closed** (bad targetId → 422, proposal stays PENDING).
- **link_add roundtrip**: propose {targetId, payload:{target}} → accept → note body gets `[[target]]`, outbound=1, graph edge=1.

## ❌ Gap found → W4a-fix
`append_audit` / `recent_audit` / `wiki_mcp_audit` table all built + store-layer-tested, but **never CALLED**
from create/accept/reject. Live: 11 proposals → audit count = 0. Spec L141/L143 "audit every call" not met
for the proposal endpoints. → W4a-fix: wire append_audit into create/accept/reject/batch (fail-SOFT add-on),
+ behavior test (create proposal → audit row appears). Re-verify audit count 0→1 on container before commit.

## Assumptions (user-review)
1. **Agent-write provenance**: an agent-proposed note_create/moc lands with `author = the proposing actor`
   (e.g. "agent:claude") unless payload sets author. — spec §2b agent-authored provenance —
   to change: set a different default in _apply note_create. (DECIDED + verified live.)
2. **trustTier on accepted agent writes = `verified` (NOT a separate candidate→promote step).**
   The human ACCEPT in the P1 queue IS the ratification, so the landed note is verified. Spec §2b mentions
   "agent writes land status=candidate / human promotes→verified" — we collapse that: the *proposal pending
   state* IS the candidate stage, and accept = promote. A second in-vault candidate tier + promote endpoint
   would be over-engineering for a single-user app (north-star: simplest implementation, full feature). —
   to change: force trustTier=candidate in _apply + add POST /wiki/notes/{id}/promote. (DECIDED.)
3. **No DELETE/purge on proposals** — accepted/rejected are terminal audit records, never purged. —
   to change: add a purge endpoint + retention policy. (DECIDED — keep all for audit.)
4. **All 6 kinds have a working apply-handler.** link_add/link_remove operate by editing the note BODY
   (links derive from body, B2) — no standalone link write exists in M1, which is correct.
5. **Audit FAIL-SOFT (W4a-fix)** — the audit append is a secondary add-on; if it raises it must NOT fail the
   primary create/accept that already succeeded (memory fail-closed-write-fail-soft-addon). —
   to change: make audit fail-closed if audit-completeness becomes a hard requirement.

## Out of scope (later sub-sprints)
- W4b MCP read-only server · W4c MCP write server (enqueue proposals) · P1 Proposal Queue screen (FE, parallel).
