# End Sprint WIKI-TRIM — gỡ 2 màn thừa /wiki/moc + /wiki/sync

Board task: #169. User CHỐT 2026-06-29 (tiếp #168): "gỡ luôn MOC" + "remove sync luôn".

## What shipped
Removed the MOC and Sync wiki screens (over-engineered for a 1-user AI-first app). Sidebar wiki nav is now Vault · Graph · Nhật ký AI. MOC notes + BE endpoints untouched.

### Changes implemented (4-step verified on disk)
- **FE — removed 2 screens** — `app/wiki/moc/page.tsx` + `app/wiki/sync/page.tsx` rewritten as redirect-only pages (`router.replace("/wiki")`, inbox-redirect convention) so old bookmarks redirect cleanly instead of falling into /wiki/[id] ("Note id không hợp lệ"). The 2 screen test files deleted; 2 redirect tests added.
- **FE — nav.ts** — removed the MOC + Sync nav items and both crumbs; updated the group + crumb comments (Vault · Graph · Nhật ký AI).
- **FE — hooks deleted (enumerated screen-only)** — `useWikiMoc` + `useWikiConflicts` + their interfaces removed from useWiki.ts (−139 lines), plus the now-unused `getWikiClusters`/`getWikiMocs`/`getWikiConflicts`/`resolveWikiConflict` imports. Confirmed no other consumer imports them (only an explanatory comment remains at useWiki.ts L317).
- **FE — KEPT all API + types (BE-backed for MCP/agent)** — `verifyWikiCitations`, `getWikiClusters`, `getWikiMocs`, `getWikiConflicts`, `resolveWikiConflict` + WikiMoc/WikiClusterList/WikiConflict/ConflictResolveInput/citation types all still in api/wiki.ts + types/wiki.ts. "Giữ API bỏ UI" — they mirror the kept BE endpoints; exported-but-unused ≠ runtime risk.
- **FE — tests updated** — Sidebar.test.tsx now asserts moc/sync links are `toBeNull` (the removal guard); nav.test.ts updated for the 2 removed items.
- **BE — confirm-only (0 files changed)** — pytest wiki layer 535 pass; the 4 kept endpoints (/clusters, /mocs, /sync/conflicts, /citations/verify) all 200 + tested. No regression from FE removal (independent surfaces).

### Verification (pass/fail)
- tsc: exit 0 ✅
- vitest (wiki+nav+Sidebar scope): 92/92 pass, 0 errors ✅ (full suite 1109 per FE report: −10 net = removed 2 screen-tests, +4 redirect-tests; act() graph-test warning is pre-existing noise)
- pytest: 535 pass, 0 changed files ✅
- grep `wiki/moc` + `wiki/sync` live FE links → ZERO (only the 2 redirect files, nav comment, Sidebar toBeNull guards, and the KEPT api/wiki.ts BE-endpoint path strings) ✅
- team-lead Chrome-gate FULL PASS: moc/sync → redirect /wiki (no error) · sidebar = Vault·Graph·Nhật ký AI (DOM js-check hasMoc=false, hasSync=false) · MOC note #29 (kind=moc) opens in Vault (badge ◇ moc + evergreen + markdown body) · console clean · API kept + BE 4 endpoints 200 ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ no API change; BE endpoints kept + tested; no manual core edit.
- **Gate 2 (Function)**: ✅ redirect tests assert observable behavior; tsc clean; vitest 100% / 0 errors; hooks removed with no dangling refs; KEPT API verified present.
- **Gate 3 (Sprint)**: ✅ this report written w/ verified counts; architect spot-checked full files on disk (redirect pages, nav diff, useWiki deletion, grep); tester + team-lead Chrome-gate pass; counts: vitest 1109 (−10 by design w/ reason), pytest 535; commit format match.

## Risks / potential errors identified
- **Exported-but-unused FE API wrappers** (getWikiClusters/getWikiMocs/getWikiConflicts/resolveWikiConflict) — intentionally kept as the typed client for the BE endpoints (MCP/agent). If a future lint flags unused exports, that's a separate, low-priority cleanup — NOT a bug. Documented so it's not mistaken for dead code.
- No data risk: MOC notes are normal notes; deleting the screen touched no note data (Chrome-gate confirmed #29 opens fine).

## Assumptions (user-review)
- **MOC + Sync screens removed; BE endpoints + FE API wrappers KEPT** — *why*: the UIs were over-engineered for a 1-user AI-first app (MOC = cluster-detector that punted drafting to the user; Sync = multi-user conflict-resolution that can't occur with one user); but the endpoints have agent/MCP value (citation-verify anti-fabrication, cluster/moc detection an agent can synthesize from) — *how to change*: to fully remove an endpoint, delete its router route + service + tests (a separate BE sprint); to restore a screen, re-add the route page + nav item + a hook over the kept API.
- **/wiki/moc + /wiki/sync redirect to /wiki** (not 404) — *why*: keeps old bookmarks working, matches the inbox-redirect convention — *how to change*: delete the redirect page files (then the routes 404).

## Commit
`feat(sprint-wiki-trim): gỡ MOC+Sync (AI-first, 1-user) — sidebar Vault·Graph·Nhật ký AI; giữ BE+API cho MCP`
Explicit-paths only (NOT template/Life Command/* or docs or app/projects/__tests__).
