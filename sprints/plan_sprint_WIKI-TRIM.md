# Sprint WIKI-TRIM — gỡ 2 màn thừa /wiki/moc + /wiki/sync

Board task: #169. User CHỐT (tiếp #168): "gỡ luôn MOC" + "remove sync luôn". App 1-user AI-first.

LOCKED:
- GỠ HẲN /wiki/moc + /wiki/sync (route + nav + crumb). Sidebar wiki còn: Vault · Graph · Nhật ký AI.
- MOC note (kind=moc) KHÔNG mất — vẫn note thường, xem trong Vault + Graph.
- GIỮ BE API (citations/verify + clusters + mocs + sync/conflicts) cho MCP/agent — chỉ bỏ UI.
- Redirect /wiki/moc + /wiki/sync → /wiki (convention inbox-redirect #168).

## Kickoff — 2026-06-29

### Enumeration (applying #168 lesson: enumerate ALL usages before deleting)
- **/wiki/moc + /wiki/sync FE refs:** moc/page.tsx + sync/page.tsx (delete) · nav.ts L99-100 (items) + L159-160 (crumbs) · Sidebar.test.tsx L106 (asserts `a[href="/wiki/sync"]` — UPDATE) · the 2 page tests (delete with routes). nav comment L89 (update).
- **Hooks — screen-only, safe to DELETE:**
  - `useWikiMoc` (useWiki.ts L359) — used ONLY by moc/page.tsx + moc.test. DELETE.
  - `useWikiConflicts` (useWiki.ts L415) — used ONLY by sync/page.tsx. DELETE.
  - (these import getWikiClusters/getWikiMocs/getWikiConflicts/resolveWikiConflict at useWiki.ts L27-30 → those imports go when the hooks go.)
- **API wrappers + types — KEEP ALL (BE-backed, for MCP/agent; "giữ API bỏ UI"):**
  - `verifyWikiCitations` (api/wiki.ts L175) — explicit KEEP (anti-fabrication, MCP). BE route `/citations/verify` (router L178) exists.
  - `getWikiClusters` (L144), `getWikiMocs` (L148) — BE routes `/clusters` (router L199) + `/mocs` (router L208) exist → KEEP wrappers + types (WikiMocList, WikiClusterList). They become unimported by FE after the hooks go, but per guardrail we keep the typed client for the kept endpoints (removing = churn + re-add later). Acceptable: an exported-but-unused lib function is not a dead-link/runtime risk.
  - `getWikiConflicts` (L181), `resolveWikiConflict` (L188) — BE route `/sync/conflicts` exists → KEEP wrappers + types (WikiConflict, WikiConflictList, ConflictResolveInput).
  - DECISION: KEEP all FE API wrappers + types. Only delete the screen-coupled HOOKS (useWikiMoc, useWikiConflicts) and the 2 routes. Rationale: the #168 lesson cuts both ways — don't over-delete on a UI-removal sprint; the BE endpoints are kept for MCP, the typed client mirrors them. (If a lint flags unused exports later, that's a separate cleanup, not this sprint.)
- **BE:** NO endpoint deletion. Verify `/clusters`, `/mocs`, `/sync/conflicts`, `/citations/verify` still pass (no regression from FE removal — they're independent, so this is a confirm-only).
- **MOC note (kind=moc):** unaffected — it's a normal note, rendered by Vault + Graph (the moc SCREEN only listed clusters/mocs; deleting it doesn't touch note data). Confirmed via the data model (moc is a noteType, not a screen-owned entity).

### Final task list
- **T1 (FE, main):** delete app/wiki/moc/ + app/wiki/sync/ (pages + tests); remove nav items L99-100 + crumbs L159-160 + update comment L89; add redirect pages /wiki/moc → /wiki and /wiki/sync → /wiki (inbox-redirect convention); delete hooks useWikiMoc + useWikiConflicts + their now-unused imports; KEEP all API wrappers + types; update Sidebar.test.tsx (drop the /wiki/sync assertion) + nav.test.ts; add 2 redirect tests. Guard: grep `/wiki/moc` + `/wiki/sync` → only redirect files + comments; tsc clean; vitest 100%.
- **T2 (BE, confirm-only):** run pytest wiki layer, confirm /clusters /mocs /sync/conflicts /citations/verify endpoints still pass (no FE-removal regression). No code change expected.

### Nav after trim
Tri thức group: Wiki Home (/wiki) · Graph (/wiki/graph) · Nhật ký AI (/wiki/proposals). (MOC + Sync removed.)

### Dispatch plan
- frontend ← T1 (the whole UI removal + redirects + hook cleanup, KEEP API).
- backend ← T2 (confirm-only, parallel, disjoint).
- tester verify → team-lead Chrome-gate (moc/sync→redirect, sidebar 3 items, MOC note opens, console clean) → commit.

## Assumptions (user-review) — filled in end_sprint
