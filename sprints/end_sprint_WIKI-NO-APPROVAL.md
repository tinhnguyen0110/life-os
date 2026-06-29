# End Sprint WIKI-NO-APPROVAL (#183) — remove all "chờ duyệt" traces (AI-first)

Board task: #183. User: AI-first has no manual approval → remove every "chờ duyệt" trace. Two surfaces (same wiki/page.tsx as #182 + proposals/page.tsx).

## What shipped
All "chờ duyệt" / approval-gate UI is gone across both wiki surfaces. The "Nhật ký AI" (proposals) page is now a PURE AUDIT log (view what the AI wrote + reverse/lùi); the reverse capability + BE endpoints are preserved (UI-gate removal only). Pure FE.

### Two parts (committed separately to respect file boundaries)
- **Home-part — committed in #182 (1b63937):** the wiki-home "{proposalCount} chờ duyệt" badge + "bạn duyệt / không bao giờ tự ghi" copy removed. (Merged into the #182 wiki/page.tsx commit to avoid a shared-file race — both touched wiki/page.tsx.)
- **Proposals-part — THIS commit:** proposals/page.tsx → audit-only:
  - Removed the "chờ duyệt" (pending) FILTER (FILTERS) — filters now AI-đã-ghi(accepted, default) / đã-reject / tất-cả.
  - Removed the batch-duyệt bar (prop-batch-bar) + the select-checkbox + the batchAccept machinery.
  - KEPT: the per-row reverse/lùi (REVERSIBLE_KINDS: note_create/moc → soft-delete appliedNoteId; edit/merge → deep-link), the accepted-default list, the agent:auto badge, the applied-note link, the honest empty-state.
  - BE endpoints untouched (accept/reject still exist server-side for any edge; just no FE gate).

### Verification (pass/fail)
- tsc exit 0; vitest proposals 19/19 (architect re-ran). Full suite 1157 per FE report. 0 errors. ✅
- grep: "chờ duyệt" filter + batch-bar GONE from proposals/page.tsx (only a removal-comment remains); reverse/lùi + accepted-default KEPT (REVERSIBLE_KINDS, canReverse, deleteWikiNote). ✅
- Only proposals/page.tsx + its test changed — no wiki/page.tsx leftover (that's the #182 commit). ✅
- team-lead Chrome-gate FULL PASS: hasChoDuyetFilter=false (AI-đã-ghi 130 / đã-reject 43 / tất-cả) · hasBatchBar=false + hasSelectCheckbox=false · 91 "Lùi (xoá note)" buttons (reverse kept) · accepted-default + agent:auto + applied-link + banner · console clean. ✅
- Combined with #182: "chờ duyệt" is now FULLY gone on both surfaces. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE; BE endpoints untouched (accept/reject server-side kept for edge cases).
- **Gate 2 (Function)**: ✅ tests assert filter+batch gone + reverse kept + accepted-default; tsc clean; 0 errors; no dropped feature (reverse preserved — mock-diff guard).
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the diff on disk + grep-confirmed + re-ran vitest; team-lead Chrome-gate pass; separate commit per file boundary.

## Risks / potential errors identified
- #183 spanned two files; the home-part shared wiki/page.tsx with #182 → MERGED into the #182 commit (race avoided); the proposals-part is its own commit. Both "chờ duyệt" surfaces now clean.
- A legacy pending proposal row (if any) is still viewable under the "tất cả" filter — just no batch-gate / no "chờ duyệt" headline. Honest.
- **PERF note (FE flagged, team-lead to track separately):** cold-start of 4 wiki/tracing endpoints is slow on first compute (streak/heatmap/derived recompute), <0.02s warm. Not a bug (warm is fast) but a cold-load "Đang tải…" UX delay. team-lead will spin a PERF-WARMUP task (BE warm-up/cache) — out of scope for #183.

## Assumptions (user-review)
- **"Nhật ký AI" = pure audit (no approval gate)** — removed the chờ-duyệt filter + batch-accept; AI writes apply directly + are audited here with a reverse/lùi affordance. BE accept/reject endpoints kept for any edge — *how to change*: re-add the filter/batch UI if a manual queue is ever wanted (the BE supports it).

## Commit
`feat(sprint-wiki-no-approval): proposals page = audit-only (bỏ chờ-duyệt filter + batch) — reverse kept`
Explicit-paths only (proposals/page.tsx + proposals test + sprint docs; the home-part is in #182's 1b63937; NOT template/Life Command/* or docs or projects-tests).
