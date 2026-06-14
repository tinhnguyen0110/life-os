# Sprint W5b — W5 MOC/Synthesize screen · END

**Status:** ✅ implemented + verified live (Rule#0, Chrome). **Commit:** (pending).

## What shipped
`/wiki/moc` — the human-facing SYNTHESIZE surface (substrate listing, per D-W5.4 + ARCH §11: no
in-app AI workspace; drafting the MOC is external Claude Code's job via MCP). Two sections:
(1) MOC notes (noteType=moc), (2) cluster candidates with members + size/density/advisory-importance
+ an honest "nhờ Claude Code nháp MOC → đề xuất vào P1 duyệt" hint (NO fabricated AI draft).

### Files (FE-only)
- NEW app/wiki/moc/page.tsx + __tests__/moc.test.tsx (7).
- MOD lib/types.ts (WikiCluster/WikiClusterMember/WikiClusterList/WikiMoc/WikiMocList — mirror W5a
  frozen shapes), lib/api.ts (getWikiClusters/getWikiMocs), lib/useWiki.ts (useWikiMoc — parallel
  load, fail-soft + 8s per-call withTimeout hang-guard), lib/nav.ts (Tri thức +MOC), Sidebar/nav tests.
- MOD vitest.config.ts — testTimeout 12000 (tester finding: the 8s hang-guard test flaked on
  cold-worker first runs vs the default 5s; bumped globally → first-run clean).

## Verified LIVE (team-lead, Rule#0)
- tsc 0 · vitest 510 (+7) FIRST-RUN CLEAN after the testTimeout fix · moc 7 def no dup.
- Chrome /wiki/moc: MOC-notes + cluster-candidate sections render; honest empty states (testid-scoped:
  no mocs / no clusters); nav "Tri thức" has MOC, resolves 200; console clean. Frontend earlier verified
  the populated case live (1 MOC note + 1 cluster with member chips + the Claude-Code-draft hint).
- **Hang-guard (the FE's good defensive add):** useWikiMoc wraps each call in an 8s withTimeout → a
  hung/errored /wiki/clusters degrades to a distinct "⚠ tạm thời không tải được" notice (NOT a lying
  "0 clusters" empty) and can't pin the screen on loading. (Swallowed-failure family — a hang shown as
  honest-empty would be a lie.) Triggered by a transient clusters hang during build (container reload,
  not a backend bug — team-lead verified clusters 8/8 fast after).

## Note
The /wiki/clusters "hang" frontend hit mid-build was a TRANSIENT container hot-reload window, NOT a
detect_clusters bug (team-lead hammered it 8×, all 200, 3–114ms). The FE hang-guard is kept as correct
defense regardless.

## A1c status
W5b completes the MOC screen part of A1c. Remaining A1c (per dispatch): chat UI (click citation → jump
note+span — pairs with A1b citation-verify), ego-graph polish, full backlink panel — future FE sprint.
