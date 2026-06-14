# Sprint P1 — Proposal Queue screen · END

**Status:** ✅ implemented + verified live (Rule#0, Chrome roundtrip). **Commit:** (pending P1 commit)

## What shipped
The human-ratify surface for the M4 trust boundary: `/wiki/proposals` lists every AI-proposed
mutation as a card; the human accepts/rejects/batch-accepts. Accept applies the mutation through
the W4a queue → it lands in the vault. Until then, nothing the AI proposes touches the vault.

### Files (frontend)
- NEW `app/wiki/proposals/page.tsx` — the queue screen (6 proposal cards rendered live, kind badge,
  actor, rationale "why", per-kind payload summary, Accept/Reject per card, batch-select +
  "Accept N đã chọn", filter tabs pending/accepted/rejected/all with live counts, trust-boundary
  explainer banner, honest empty state).
- NEW `app/wiki/proposals/__tests__/proposals.test.tsx` — 9 tests.
- MOD `lib/types.ts` (Proposal/ProposalKind/ProposalStatus, mirrored from frozen W4a contract) ·
  `lib/api.ts` (getProposals/acceptProposal/rejectProposal/acceptBatch) · `lib/useWiki.ts`
  (useWikiProposals hook) · `lib/nav.ts` ("Proposals" → /wiki/proposals in Tri thức group) ·
  `lib/icons.tsx` · `lib/tokens.css` (ported proposal-card styles from the mock) ·
  Sidebar.test.tsx + nav.test.ts (route count + explicit /wiki/proposals assert).

## Verified LIVE (team-lead, Rule#0 — Chrome roundtrip, not field-read)
- tsc 0 · vitest 496/496 (+9) · 9 P1 tests no dup-name · console clean.
- nav "Tri thức" now has Proposals; /wiki/proposals → 200.
- Chrome render: 6 live pending cards (kind badges, actor, rationale, payload summary, Accept/Reject,
  batch-select, filter tabs + counts chờ-duyệt/accept/reject/tất-cả, trust-boundary banner).
- **ACCEPT ROUNDTRIP (the key gate, write-form-roundtrip-verify):** clicked Accept on a note_create
  proposal in the UI → `POST /wiki/proposals/26/accept` 200 → refetch `GET ?status=pending` →
  the note "Zettelkasten" ACTUALLY LANDED in the vault (totalNotes 0→1, searchable, id assigned),
  proposal flipped accepted (appliedNoteId set), pending count 7→6, the card left the queue.
  The AI→propose→human-accept→vault-write chain works end-to-end through the UI.

## Note (transient, not a bug)
First Accept click via a stale element-ref did not register (Next hydration/ref timing); a
coordinate click immediately after fired the correct POST+refetch. FE wiring is correct (network
trace: OPTIONS+POST accept 200 → GET pending). No code issue.

## Assumptions (user-review)
- P1 is ratify-only: humans do NOT create proposals from the UI (that's the AI's job via MCP).
  The screen accepts/rejects/batches — matches the trust model (human curates, AI proposes). —
  to change: add a manual "propose" affordance (unlikely needed; humans edit notes directly).

## Out of scope
- W4b/W4c MCP servers (backend, parallel). note_edit diff is a simple before/after, not a diff lib.
