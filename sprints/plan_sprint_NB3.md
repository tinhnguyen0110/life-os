# Sprint NB3 — wiki-proposal read-back (the NG2 follow-on asymmetry) + proposalCount=0 bug

> Blank-context dogfood (user's refined trick) found this, team-lead Rule#0-verified live.
> Memory: `blank-context-dogfood-2026-06-15`. Backend-only. Sibling of original G1 wiki-MCP asymmetry + [[built-but-not-wired-gap]].

## Kickoff — 2026-06-15 (architect)

### The gap — verified on disk (kickoff)
NG2 surfaced the wiki WRITE tools (`wiki_propose_*`) on the whole-app write catalog → they correctly enqueue to the `wiki_proposals` queue. But the **read-back is asymmetric**:
- `read_server.py:122-123` — `check_proposal_status` / `list_my_proposals` / `proposal_stats` read ONLY `mcp_servers.proposals_store` (`_proposal_get`/`_proposal_list`/`_proposal_counts`) = the **whole-app `agent_proposals` queue**. They have NO view of `wiki_proposals`.
- Verified consequence (team-lead, live): `wiki_propose_note` → #71 lands in wiki_proposals (pending, write works) BUT `check_proposal_status(71)` → `{found:false}`, `list_my_proposals`/`proposal_stats` don't show it, `wiki_overview.proposalCount` reads 0.
- So an agent saves a wiki note and **cannot confirm it landed or whether the user accepted it.** NG2 surfaced the write but not the symmetric read-back.

### Fix primitives EXIST (no new logic — confirmed on disk)
- `modules/wiki/proposals_service.py`: `get_proposal(id) -> dict|None` (141), `list_proposals(status=None) -> list[dict]` (145), `count_by_status() -> dict[str,int]` (149). The read-back primitives are already there — just need MCP wrappers.
- `read_server.py` TOOLS is a flat dict (708) → adding tools = add fns + dict entries; the catalog auto-derives from TOOLS (no second list to maintain).
- **Bonus real bug:** `modules/wiki/reader/overview.py:55` HARDCODES `"proposalCount": 0,  # AI proposals land at M4`. M4 shipped long ago; proposals are real now → wiki_overview always reports 0 pending. Wire it to `proposals_service.count_by_status()`.

### 🔑 THE DECISION (architect call — decide-and-log) → Option B (dedicated namespaced wiki read tools)
**Add `wiki_proposal_status(proposal_id)` + `wiki_list_proposals(status=None)` as new READ-ONLY MCP tools on read_server, each wrapping the existing `proposals_service` read fns (wiki-queue scoped). + fix the hardcoded proposalCount.**

Why B over A (unify `check_proposal_status` to also check wiki_proposals):
1. **Symmetry with NG2** — we surfaced the wiki WRITE namespaced (`wiki_propose_*`, own queue, own ratify surface). The read-back must mirror that: namespaced, same queue. A namespaced write with an un-namespaced read-back is the asymmetry that *created* this bug.
2. **`check_proposal_status(id)` is AMBIGUOUS across two queues** — proposal id `71` can exist in BOTH `agent_proposals` AND `wiki_proposals` (separate autoincrement tables). A unified reader resolving one id non-deterministically (or returning two hits) is a footgun. Namespaced tools keep each id unambiguous *within its queue*.
3. The two queues are intentionally separate ratify surfaces (the P1 wiki screen vs the whole-app queue) — their READ paths should stay separate just like their WRITE paths.

### Final task list (single backend lane)
- **NB3 [backend]** — three changes, all read-only:
  1. `wiki_proposal_status(proposal_id)` MCP tool — wraps `proposals_service.get_proposal(int(id))`; mirror `check_proposal_status`'s shape (`found`/`proposalId`/`status`/`appliedRef`/`applyError`/`decidedBy`/`decided` + whatever the wiki proposal dict carries — kind/targetId/actor). Bad/unknown id → `{found:false, proposalId:...}` (honest, NG4-style, no raw ValueError).
  2. `wiki_list_proposals(status=None, limit=50)` MCP tool — wraps `proposals_service.list_proposals(status)`; newest-first, optional status filter, empty → `{proposals: []}`. Mirror `list_my_proposals`.
  3. `modules/wiki/reader/overview.py:55` — replace `"proposalCount": 0` with the real pending count from `proposals_service.count_by_status().get("pending", 0)` (import at module top, no circular-import — overview already in the wiki package; if circular, lazy-import inside the fn). Drop the stale `# AI proposals land at M4` comment.
  - Register both new fns in TOOLS dict (catalog auto-includes them; regen CATALOG.md if it's a committed artifact).

### Capability gate (MUST stay read-only)
- Both new tools are READ-ONLY (wrap `get_proposal`/`list_proposals` — no `create_proposal`/`accept`/`reject`/`apply`). The existing read-server no-write AST/namespace gate (`test_mcp_read.py` WRITE_SYMBOLS) MUST still pass with the two new fns added — they import NO write/mutate symbol from proposals_service (only the 3 read fns). If the gate flags anything, the tool reached a forbidden symbol = fix the tool, not the gate.

### Verification (gate)
- After a `wiki_propose_note` enqueues #N: `wiki_proposal_status(N)` → `{found:true, status:"pending"}` (the asymmetry closed); `wiki_list_proposals()` includes #N; `wiki_overview.proposalCount` reflects the real pending count (NOT 0).
- Distinguishing case: `wiki_proposal_status(N)` found:true AND `check_proposal_status(N)` for the SAME N (if not in agent_proposals) → found:false — proving the two readers are queue-scoped, not collapsed.
- Capability: read-server WRITE_SYMBOLS gate green (0 write-symbol leak); e2e + full suite green. Venv test path, baseline 1455.
- Clean up any live-verify proposal created (reject it — live-write-test hygiene, [[test-writes-pollute-prod-runtime-store]]).

## Assumptions (user-review)
- Wiki proposal read-back is exposed as DEDICATED namespaced MCP tools (`wiki_proposal_status`/`wiki_list_proposals`), NOT by unifying `check_proposal_status` across both queues — because a proposal id is ambiguous across the two separate queues, and to mirror NG2's namespaced write surface. The two proposal queues stay separate in BOTH read and write paths.
- `wiki_overview.proposalCount` now reflects the real pending count from `count_by_status()` (was hardcoded 0 with a stale "land at M4" comment — M4 shipped).
