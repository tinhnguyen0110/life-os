# Sprint WIKI-NO-APPROVAL — remove all "chờ duyệt" traces (AI-first)

Board task: #183. User: AI-first has no manual approval → remove every "chờ duyệt" trace from the wiki.

## Kickoff — 2026-06-29

### Two surfaces (found on disk)
1. **Wiki Home** (wiki/page.tsx): the "{proposalCount} chờ duyệt" badge + "bạn duyệt / không bao giờ tự ghi" copy. ⚠️ SAME FILE as #182 (in-flight inbox-refine removal).
2. **Proposals page** (proposals/page.tsx): the "chờ duyệt" pending FILTER + the batch-duyệt bar.

### Decision — split by file to avoid a shared-file race
- **Home-part → MERGED into #182** (both edit wiki/page.tsx → one pass, one commit = 1b63937). The chờ-duyệt badge/copy removed alongside the inbox-refine panel. Avoids two sprints editing wiki/page.tsx in parallel (the shared-file-race lesson).
- **Proposals-part → this sprint's own commit** (proposals/page.tsx, disjoint file): remove the chờ-duyệt filter + batch bar → "Nhật ký AI" = pure audit (accepted-default + reverse/lùi). KEEP reverse + BE endpoints (UI-gate removal only).

### Task list
- Home-part: done in #182 (1b63937).
- **T1 (FE, this commit):** proposals/page.tsx → remove "chờ duyệt" filter + batch-duyệt bar; keep reverse/lùi + accepted-default + BE endpoints; honest empty.

### Dispatch
- frontend ← T1 (proposals/page.tsx), dispatched after #182 committed (same agent, disjoint file, one-task-at-a-time). team-lead Chrome-gate per surface.

## Assumptions — in end_sprint_WIKI-NO-APPROVAL.md
