# Sprint WIKI-STALE-DETECTOR — read-only wiki staleness flags (Cairn #41, SPEC A6)

> Created 2026-06-21 by architect (NEVER-FREE: designed while backend did #33/#34). Architect-design task (KHÔNG chờ-user, reversible, read-only). DESIGN to team-lead before any build (net-new feature shape). Self-curation pair with cairn #326.

## Objective
The wiki has no stale/contradiction detection. #41 = a READ-ONLY detector that flags notes likely to be forgotten-but-important (stale) + a v1 contradiction-candidate heuristic, so an agent (or the user) knows what to revisit. NO auto-fix — flags only.

## Grounded against the live schema
- Note HAS `created` + `updated` (ISO-8601 UTC strings) ✓ → staleness is computable.
- `Status = fleeting | developing | evergreen`; `NoteType = concept | literature | moc`; `TrustTier = verified | candidate`.
- `reader.backlinks(note_id)` → `{linked (inbound), unlinked, outbound}` → "has an important backlink" = `len(linked) >= 1` (something points TO it = it matters).
- **NO "pain" concept in the wiki** — the task's "pain open quá lâu" refers to a DIFFERENT module (projects/career pains), NOT wiki notes. So #41's wiki detector scopes to NOTE staleness; a cross-module "pain open too long" check is OUT (separate task if wanted).

## The detector (DECIDED — decide-and-log; team-lead sanity-check)
A read-only `reader.stale_notes()` (and a `wiki_stale` MCP/REST surface) returning two lists:

### 1. STALE notes
A note is `stale` if ALL:
- `now - updated > N days` — N = a CONFIG KNOB `staleThresholdDays` (default **90** — a quarter; long enough not to nag, short enough to catch genuinely-forgotten notes; team-lead: make it a knob so the user tunes without a code change), AND
- `status == "evergreen"` (an evergreen note is MEANT to be a stable, refined, load-bearing note — if it's gone 90d untouched it may be drifting out of date; a `fleeting` note is expected to be raw/transient → NOT flagged; a `developing` note is in-progress → NOT flagged, OR flagged at a longer threshold — decide-and-log: v1 flags evergreen only, the clearest signal), AND
- `len(backlinks.linked) >= 1` (something links to it → it's load-bearing, worth keeping current; an orphan evergreen is a different concern handled by `overview.orphans`).
Output per note: `{id, title, updated, daysSince, inboundCount, status}`, sorted daysSince DESC (stalest first).

### 2. CONTRADICTION-CANDIDATES (heuristic v1 — deterministic, NO AI)
v1 = the SIMPLEST honest signal: a pair of notes that **link each other** (mutual `[[ ]]`) AND have **divergent trustTier** (one `verified`, one `candidate`) on heavy FTS content overlap — i.e. two connected notes where one is trusted + one is unverified covering the same ground → a human should reconcile. (decide-and-log: v1 is a CANDIDATE flag for human review, NOT a claim of contradiction — no AI judges content. Keep v1 tiny; richer contradiction detection is a later iteration.)
Output per candidate: `{pair: [id1, id2], reason: "verified+candidate on overlapping linked notes"}`.

## Scope
IN: `reader.stale_notes()` (the 2 lists) + a read surface (REST `GET /wiki/stale` + MCP `wiki_stale` → add to the #24 parity gate). Reuse `updated`, the links table, FTS. Tests.
OUT: any auto-fix/auto-archive (flags only); AI content-judgment; the cross-module "pain" check; a scheduler routine (v1 is on-demand; a periodic nudge is a later add).

## ⚠️ PERF (architect note — do NOT call backlinks() per-note)
Grounded the data path: `reader.backlinks(note_id)` calls `links_to(note_id)` AND builds per-source snippets (`_mention_snippet`/`_title_of`) — EXPENSIVE, and the stale-detector only needs the inbound COUNT, not snippets. Calling backlinks() for every evergreen note = O(n) queries + wasted snippet work. INSTEAD: the detector must use a **bulk inbound-count** — ONE `GROUP BY target_id` query over the links table (resolved edges) → `{target_id: count}`, joined in-memory against `all_notes()` (queries.py already has `all_notes()`). Backend likely needs to ADD a `store.inbound_counts()` (a single GROUP BY) — call that out in the dispatch so backend doesn't loop backlinks(). The detector is then 2 queries (all_notes + inbound_counts), not n×backlinks.

## HARD GATE (distinguishing)
- An `evergreen` note `updated` 100d ago WITH an inbound link → flagged stale; the SAME note `updated` yesterday → NOT flagged; a `fleeting` note 100d old → NOT flagged (status gate); an evergreen 100d old with ZERO inbound → NOT flagged (it's an orphan, not stale-important). [4 distinguishing axes: age, recency, status, inbound]
- contradiction v1: a verified↔candidate mutually-linked overlapping pair → flagged; two verified linked notes → NOT.
- read-only (no mutation); REST≡MCP byte-identical (#24 gate). pytest green, mypy clean.

## Assumptions (user-review)
- **wiki stale = evergreen + updated>90d + ≥1 inbound backlink** (an important note gone quiet). fleeting/developing NOT flagged (expected to churn / in-progress); orphan-evergreen is a separate `overview.orphans` concern. **How to change:** the N threshold + the status/inbound predicate in stale_notes.
- **contradiction-candidate v1 = verified↔candidate mutually-linked overlapping pair** (a human-review FLAG, deterministic, NOT an AI contradiction claim). **How to change:** the heuristic in stale_notes (richer detection = later iteration).
- read-only detector, NO auto-fix; on-demand (no routine v1).

## Notes
- Architect-design task; bring to team-lead before build dispatch. If small, may build directly post-approval. Separate commit `feat(sprint-WIKI-STALE-DETECTOR)`.
- Self-curation pair with cairn #326. NEVER-FREE: designed during backend's #33/#34.
