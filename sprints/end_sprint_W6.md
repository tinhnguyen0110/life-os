# Sprint W6 — END

> A1b (citation post-verify) + A1a (M3 sync). Split commits: T1 committed first (done+verified),
> T2 (A1a) committed separately after its own review. This doc covers T1; T2 section appended when it lands.

---

## T1 — A1b Citation post-verify · ✅ SHIPPED + verified live (Rule#0, twice — architect + team-lead)

**Commit:** `feat(sprint-W6): A1b citation post-verify` (hash recorded below at commit).

### What shipped — the anti-fabrication gate (Trụ C, spec L120-121)
A stateless, deterministic citation verifier the EXTERNAL Claude Code agent calls (via MCP or REST)
before presenting an answer. M2 in-app chat was dropped (chat = external agent over MCP), so the
post-verify lives as a read-only service, NOT inside a chat endpoint. Per `{claim, noteId, span}`:
note must exist + the cited span must actually occur in it, or the citation is rejected/flagged.

### Files
- `modules/wiki/citations.py` — pure `verify_citations(claims)` + `_verify_one` + `_normalize` (no HTTP, no mutation).
- `modules/wiki/router.py` — `POST /wiki/citations/verify` → `ok(data={results, summary})`.
- `modules/wiki/schema.py` — `Citation` + `CitationVerifyInput` (max_length guards; empty-list valid).
- `modules/wiki/mcp/read_server.py` — `wiki_verify_citations` read tool (9th tool; AST-no-write gate STILL holds — imports the bare pure fn, leaks no write symbol).
- `modules/wiki/mcp/README.md` — documents the citation contract (the tool IS the contract).
- `tests/test_wiki_citations.py` (14) + `tests/test_wiki_mcp_read.py` (parity + no-write gate updated for 9 tools).

### Algorithm (deterministic, no AI/vector)
Per claim, in order: noteId None → `ungrounded` (no_citation) · `resolve_note` (follows D6 redirect
chain, depth-capped 10 + cycle-guarded) None → `rejected` (note_not_found) · empty/whitespace span →
`weakly_grounded` (no_span; names a real note, quotes nothing) · else normalize both sides
(`" ".join(s.split())` — collapse whitespace+newlines, CASE-SENSITIVE) + substring-match against
`title + "\n" + body` → in → `verified` (resolvedNoteId set iff a redirect was followed) · not in →
`rejected` (span_not_in_note — the anti-fabrication rejection). Summary tallies the four statuses + total.

### Verified LIVE (both architect + team-lead, independently)
- **pytest 947 (+14)**, 0 fail / 0 error (full tail), 14 defs==collected no dup, mypy clean.
- **AST no-write gate holds** with the 9th read tool (read_server imports NO write/mutation symbol).
- **Distinguishing case (the teeth), live on :8686**: same real note — a real span → `verified`; a
  fabricated span → `rejected/span_not_in_note`. A collapsed note-exists-only impl verifies the fake;
  this rejects it. + null→ungrounded, ""→weakly_grounded, nonexistent→note_not_found. 5-case summary correct.
- **Extra edge cases (architect hunt)**: unicode span (body + title) → verified; span crossing the
  title/`\n`/body boundary → verified (permissive by design); twice-merged citation (old→mid→new) →
  resolves to final live note via the redirect chain.

## Assumptions (user-review)
1. **A1b placement = stateless verify service** (`POST /wiki/citations/verify` + `wiki_verify_citations`
   MCP read tool), NOT a check at proposal-accept and NOT in an in-app chat (M2 dropped). — why: chat
   is external Claude Code over MCP; the verify is the deterministic guarantee the agent is expected to
   call. — to change: only if an in-app chat is ever built (it won't be this build).
2. **Span match = literal substring vs normalized `title + "\n" + body`, case-SENSITIVE, no `^block-id`.**
   — why: block anchors (D7) were never built; substring delivers the anti-fabrication guarantee simplest.
   — to change: add block-id assignment at write time + anchor-aware matching (a whole sub-feature).
3. **Title is IN SCOPE for span matching** (a citation to a titular claim verifies; a span can even
   straddle the title→body boundary because normalize joins them with a single space). — why: titles
   are claims (Matuschak "titles are APIs"); permissive verify never false-rejects a legit quote and
   never passes a fabricated one. — to change: match body-only (stricter, would reject title quotes).
4. **`weakly_grounded` is a distinct 4th tier** (note real, no span) — surfaced, NOT rejected. — why:
   the agent gets credit for naming a real note even without an exact passage; the user decides. — to
   change: fold into `verified` (laxer) or `rejected` (stricter).

## T2 — A1a M3 sync (option B) · ✅ SHIPPED + verified live (Rule#0 — architect; team-lead spot-check pending)

**Commit:** `feat(sprint-W6): A1a M3 sync — block-LWW merge + conflict detect/surface (option B)` (hash at commit).

### What shipped — the cross-device merge MECHANISM + a provable gate (spec §M3, D3=M3)
The op-log + single-writer already exist (M1). M3 adds the cross-device MERGE layer: many device
op-streams → block-level Last-Writer-Wins convergence, with TRUE conflicts DETECTED + surfaced (never
silently overwritten). 0 data loss = every block from every stream is either in the merged doc OR
recoverable from a conflict record. Option B: ship the mechanism + the convergence/conflict gate;
defer the parts that only matter once a 2nd physical device exists.

### Files
- `modules/wiki/sync.py` — PURE `merge_streams` (commutative, order-independent) + `split_blocks`/`join_blocks` + `BlockEdit`/`Conflict` + `delete_edit` (tombstone) + `merge_and_record` (impure bridge → persists conflicts).
- `modules/wiki/sync_store.py` — `wiki_devices` (registry) + `wiki_sync_cursor` (per-device offline-resume point) + `wiki_sync_conflicts` (every version kept → loser recoverable).
- `modules/wiki/router.py` — 5 endpoints: POST/GET `/sync/devices`, GET `/sync/conflicts`, POST `/sync/conflicts/{id}/resolve` (resolve writes the chosen content THROUGH service.update_note = single-writer).
- `modules/wiki/schema.py` — `DeviceRegisterInput` + `ConflictResolveInput`.
- `tests/test_wiki_sync.py` (17) — block split, convergence, commutativity, the conflict-recoverable teeth, clock-skew tiebreak, rename+edit, delete-vs-edit, idempotent resume, device/cursor, live API surface+resolve+404.

### Algorithm (block-LWW, deterministic, no AI)
Block = blank-line-run-delimited paragraph; identity = INDEX. Per (noteId, blockIndex): one content or
same content across streams → take it (idempotent resume = no-op) · divergent content ≥2 → CONFLICT:
LWW winner (max `(ts, device)` — deterministic tie-break for clock skew) into the merged doc, AND a
Conflict record keeps every distinct version (loser recoverable). Whole-note delete = tombstone
BlockEdit at index -1; delete-on-A vs edit-on-B → note-scope conflict (ASK), tombstone never
materialized as body. merge is COMMUTATIVE (merge(A,B)==merge(B,A)).

### Verified LIVE (architect, Rule#0 — independent of backend's report)
- **full pytest 964 passed / 6 skipped / 0 fail / 0 error** (full tail read), test_wiki_sync 17 def==collected, mypy clean (sync + sync_store).
- **THE GATE (independent re-run):** commutative `merge(A,B)==merge(B,A)` TRUE · non-conflicting 2-stream edits → `["alpha","shared","beta"]` 0 data loss, 0 conflicts · divergent same block → winner in doc + BOTH versions kept (loser recoverable). A take-latest-everywhere impl passes convergence but FAILS loser-recoverable — the distinguishing teeth.
- **LIVE API on :8686:** device register/list works; `/sync/conflicts` honest-empty; resolve writes through the single-writer.

## Assumptions (user-review) — T2
5. **A1a = option B (mechanism, not full multi-device).** Shipped: block-LWW merge + conflict
   detect/surface + device registry + offline-resume cursor. — why: single-user, currently single-device
   — building id-prefix migration + FE conflict UI + real transport for a 2nd device that doesn't exist
   is premature (north-star). — DEFERRED + how-to-add:
   - **id-prefix migration** (`47`→`d-47`): add a prefix column, existing ids default to the desktop
     prefix (NOT a rebuild — spec D1 M3 path). Add when a 2nd device generates ids concurrently.
   - **FE conflict-resolution UI**: consumes `GET /wiki/sync/conflicts` + the resolve endpoint. Build in
     the FE sprint (A1c) when a real conflict can occur.
   - **real device-to-device transport**: `merge_streams` takes op-streams as INPUT; how they arrive over
     a wire (HTTP sync protocol) is deferred until there are 2 devices.
6. **Block identity = index** (not a stable block-id / `^anchor`). — why: simplest deterministic unit for
   single-user localized edits. — to change: assign stable block ids at write time (couples to the
   never-built D7 `^block-id` lifecycle).
7. **delete-vs-edit = conflict (ASK)**, never silent delete or resurrect; tombstone at block -1, never
   materialized as body. — to change: a policy decision (delete-wins / edit-wins) — but ASK is the
   safe single-user default.
