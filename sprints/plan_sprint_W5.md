# Sprint W5 — SYNTHESIZE + MOC (the spec's "payoff") · plan

> Spec L64 SYNTHESIZE: detect cluster → synthesis workspace → draft MOC note linking members +
> articulating throughline; surface contradictions ("these two notes disagree"). "Challenge my
> thinking," not "summarize." L51: LLM detects clusters → proposes MOCs → human ratifies.

## Architecture split (CRITICAL — the LLM is EXTERNAL Claude Code via MCP, NOT in-app)
Per ARCH §11 + the whole build: NO embedded LLM. So SYNTHESIZE splits into:
- **In-app (this sprint): the SUBSTRATE** — deterministic, no-AI cluster DETECTION (graph-based, not
  vector), a first-class `moc` note type, MOC + cluster-candidate listings, and MCP read tools so
  external Claude Code can pull cluster members. NO fake AI: clustering is real graph community
  detection; the "draft MOC scaffold + articulate throughline + surface contradictions" is the LLM's
  job, done by Claude Code over MCP (read cluster → propose_moc with the synthesized body).
- **The LLM part (already enabled by M4):** Claude Code reads `wiki_clusters` (W5a) → reads the member
  notes (wiki_get_note) → drafts an MOC + spots contradictions → `propose_moc(...)` (W4c) → human
  ratifies in P1. The loop already exists; W5 gives it the cluster substrate + the MOC surface.

This keeps the litmus: clusters are detected by CODE (deterministic), MOCs are PROPOSED by the LLM,
RATIFIED by the human. No in-app AI, no fake clusters.

## Decisions (decide-and-log)

### D-W5.1 — cluster detection = graph community detection, NO vector (L155 vector is Phase-2 >5k)
Use connected-components + intra-cluster link-density on the RESOLVED-edge graph (the store already
has resolved_neighbors/degree/edges_among). At M1 scale (<5k notes) a label-propagation or
connected-component pass is cheap + deterministic. A "cluster" = a connected group of ≥3 notes with
internal link-density above a threshold (configurable, core/config). Output ranked by size×density.
NOT Adamic-Adar / cosine (Phase-2). **Why:** real signal, no vector dep, no fake AI. **How to change:**
swap the algorithm behind `detect_clusters()`; threshold in config.

### D-W5.2 — `moc` becomes a first-class noteType
Add `"moc"` to the NoteType Literal (concept|literature|**moc**). The W4a `moc` PROPOSAL kind already
creates a note; make it set noteType="moc" so MOCs are listable/filterable + the graph can style them.
**Why:** an MOC is "a writable workstation ≠ backlinks" (L38) — needs to be distinguishable. **How to
change:** it's an enum member; MOC notes are otherwise normal notes.

### D-W5.3 — C3 importance = ADVISORY, not authoritative (RESOLVE the open decision)
Spec L242/278 open question. DECIDE: importance/cluster-rank is **advisory** — it orders MOC
candidates + ranks retrieval, but NEVER gates pruning or auto-deletes (that would be the LLM
exercising editorial authority over salience → violates north-star). The human (or the agent via a
proposal) decides what to merge/prune; importance only SUGGESTS. **Why:** north-star — code/LLM
surfaces, human disposes. **How to change:** would require a deliberate "authoritative importance"
decision (don't).

### D-W5.4 — contradiction surfacing is LLM-side, substrate is cluster-membership
We do NOT build an in-app contradiction detector (that's LLM judgment / NLI, Phase-2 L155). The
substrate exposes cluster members (+ their content via wiki_get_note); Claude Code reads them and
surfaces "these two disagree" when it drafts the MOC. W5 just makes the members easy to pull.

## Scope
### W5a — backend substrate (GATING)
- `detect_clusters()` (graph community detection, D-W5.1) + `GET /wiki/clusters` (MOC candidates:
  [{members:[ids+titles], size, density, suggestedTitle?}], ranked). Populate ego_graph `clusters`
  too (was []).
- `"moc"` noteType (D-W5.2) + `GET /wiki/mocs` (list MOC-type notes) + the moc proposal apply sets
  noteType=moc.
- MCP read tool `wiki_clusters` on the read server (so Claude Code pulls candidates) — still no-write.
- importance: a simple advisory `importance` derived field on cluster candidates (size×density), NOT
  stored-authoritative (D-W5.3).

### W5b — frontend W5 MOC screen (after W5a freezes shapes)
- `/wiki/moc` screen: (1) list existing MOC notes, (2) cluster candidates ("MOC suggestions" — these
  notes cluster, consider an MOC; with a "ask Claude Code to draft" hint since drafting is LLM-side),
  (3) link to each cluster's members. nav "Tri thức" + MOC entry. Honest empty states (no clusters
  yet / no MOCs yet). PORT the mock's W5 styling if present.

## Gates
- W5a: clusters detected on a real linked graph (≥3-note cluster surfaces; isolated notes don't);
  /wiki/clusters ranked; moc noteType round-trips; /wiki/mocs lists only mocs; wiki_clusters MCP tool
  returns same as REST + read-server still no-write (AST gate holds); 200-note <1s (perf gate);
  pytest+mypy green, no dup.
- W5b: Chrome — clusters render as MOC suggestions, MOC list shows moc notes, empty states honest,
  nav resolves; tsc+vitest green.
- E2E (the synthesize loop): seed a linked cluster → GET /wiki/clusters surfaces it → (Claude Code
  would propose_moc) → simulate propose_moc → accept in P1 → MOC note appears in /wiki/mocs + W5.
