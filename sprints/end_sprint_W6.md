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

## T2 — A1a M3 sync · (pending — appended after backend lands + architect review)
