# End Sprint WIKI-HOME-TRIM (#182) + WIKI-NO-APPROVAL home-part (#183)

Board tasks: #182 (remove "Inbox cần refine") + #183 home-part (remove "chờ duyệt" traces). Both touch wiki/page.tsx → done in ONE pass / ONE commit to avoid a shared-file race.

## What shipped
Wiki Home is now AI-first-clean: no "Inbox cần refine" triage panel, no "chờ duyệt" proposal badge/copy; the orphan-sweep + op-log go full-width. KPI tiles, #94 bulk-select, the audit-link, and the BE payload all preserved. Pure FE.

### Changes implemented (4-step verified on disk + gate)
- **#182 — remove "Inbox cần refine" panel** + orphan-sweep → FULL-WIDTH (grid 2col→1col); dropped the now-unused `inbox` const + InboxRow import. Notes still in Vault/Graph (only a home render removed).
- **#183 home-part — remove "chờ duyệt"** — the `wproposal-mini` panel ("{proposalCount} chờ duyệt" + the "bạn duyệt / không bao giờ tự ghi" copy) removed; the file header doc updated. AI-first = no manual approval, so the approval framing is gone. Op-log → full-width.
- **KEPT**: #94 bulk-select (full-width orphan list), KPI "Fleeting" tile (different metric — fleeting-STATUS, not the inbox-queue), the "→ Nhật ký AI" audit-link, the empty-vault state. BE untouched — `overview.inbox`/`proposalCount` stay in the payload (life_brief etc.), only the FE render dropped.

### Verification (pass/fail)
- tsc exit 0; vitest vault 12/12 (architect re-ran). Full suite 1157 per FE report. 0 errors. ✅
- grep confirms the live "Inbox cần refine" + "chờ duyệt"/"bạn duyệt"/"không bao giờ tự ghi" strings are GONE (only removal-documenting comments remain). ✅
- KEEP verified: #94 bulk-select state+render, KPI Fleeting, audit-link, proposalCount read-only-in-payload. ✅
- Only wiki/page.tsx + vault.test changed — no tracing leftover from #181 (already committed 22bfa93). ✅
- team-lead Chrome-gate FULL PASS (DOM + eyes-on): hasInboxRefine=false · hasChoDuyet=false + hasBanDuyet=false · orphan-sweep full-width + "14 cô lập" + Chọn-nhiều (#94) · op-log full-width · KPI Fleeting present (39) · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE; BE payload untouched (proposalCount/inbox kept).
- **Gate 2 (Function)**: ✅ tests assert the panels gone + KPI/bulk kept; tsc clean; 0 errors; no dropped feature (bulk + audit-link preserved — mock-diff guard).
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the diff on disk + grep-confirmed strings gone + re-ran vitest; team-lead Chrome-gate pass; one commit for the shared file (no 2-commit race).

## Risks / potential errors identified
- #182 + #183-home both touched wiki/page.tsx → MERGED into one pass/commit (team-lead caught the shared-file collision early). Avoided the parallel-shared-file race (the lesson). The #183 PROPOSALS part (proposals/page.tsx) is a separate file → its own commit, dispatched next.
- overview.proposalCount/inbox kept in the BE payload (life_brief may consume) — only the FE render removed. Honest.

## Assumptions (user-review)
- **Wiki Home drops inbox-refine + chờ-duyệt panels (AI-first)** — *why*: AI writes apply directly + are audited at "Nhật ký AI"; no manual triage/approval → those panels were wrong. Notes still in Vault/Graph; BE payload unchanged — *how to change*: re-add the panels in wiki/page.tsx (data still in overview).
- **Orphan-sweep + op-log full-width** (was 2-col with the removed panels) — layout-only.

## Commit
`feat(sprint-wiki-home-trim): bỏ inbox-refine + chờ-duyệt (AI-first) — orphan/op-log full-width`
Explicit-paths only (wiki/page.tsx + vault.test + sprint docs; NOT the #181 tracing files [already in 22bfa93], NOT template/Life Command/* or docs or projects-tests). The #183 proposals-page part is a SEPARATE commit.
