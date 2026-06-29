# End Sprint WIKI-AIFIRST — bỏ chế độ duyệt, AI-first ghi thẳng tri thức

Board task: #168. User CHỐT 2026-06-29.

## What shipped
AI-first wiki: removed the Inbox/triage screen, reframed the Proposals screen into an AI write **audit-log** ("Nhật ký AI"), confirmed the autonomous-write mechanism was already live.

### Changes implemented (4-step verified on disk, full functions read)
- **BE T1 (verify/guard only — no production code)** — `backend/tests/test_wiki_mcp_write.py` (+57 lines, 535 pytest pass, +3 net). New real-behavior assertions: autonomous default ON (fresh config) · MCP propose auto-applies + keeps `accepted` record (decidedBy=`agent:auto`, appliedNoteId==noteId, kind, all 7 audit fields) · REST propose does NOT auto-apply even with autonomy ON (asserts the distinguishing condition, not a false-green) · soft-delete reverse recoverable. The mechanism (autonomous default True, REST F1-S1 boundary, audit record kept) was ALREADY shipped (#25 write-through era) — this sprint only locks it with tests.
- **FE T2 — remove /wiki/inbox** — nav item + crumb removed; `[id]` back-button → `/wiki` ("Vault"); `_rows.InboxRow` → opens note directly at `/wiki/{id}`; Vault page inbox links removed/repointed (the "new note" CTA → `/wiki/proposals`; "triage →" → "mở note để refine" hint); empty-state copy updated. inbox.test.tsx deleted (route gone).
- **FE redirect** — `app/wiki/inbox/page.tsx` rewritten as a redirect-only page (`router.replace("/wiki")`), matching the /graveyard + /dev-activity convention. Keeps old bookmarks alive (was rendering a confusing "Note id không hợp lệ"). New `inbox-redirect.test.tsx`.
- **FE T3 — proposals → "Nhật ký AI" audit-log** — default filter `accepted`; title/sub/banner reframed honest (autonomous ON, this is the log not a gate); accept/reject demoted (kept per-row for rare legacy pending, no headline batch-gate); REVERSE per accepted row: note_create/moc → "Lùi (xoá note)" SOFT-delete `appliedNoteId` (recoverable, fail-closed) + "khôi phục" deep-link; edit/link/merge → manual-refine deep-link + honest "chưa có version-undo" hint; per-filter honest empty-state.
- **FE T4 — collapse/markdown for audit-card content** (user request, same file) — long `content` (>120 chars OR newline) renders collapsed (3-line raw clamp + "▸ xem thêm") → expand to full `WikiMarkdown` (REUSED, not a new renderer). Scoped `.wprop-*` CSS only; overflow:hidden confined to the clamped preview (toggle is a sibling outside → never clipped). Short content renders inline, no toggle.

### Verification (pass/fail)
- tsc: exit 0 ✅
- vitest (wiki+nav+useWiki scope): 87/87 pass, 0 errors / 0 unhandled ✅ (full-suite 1114 pass per FE report; the graph-test act() warning is pre-existing noise, not this sprint)
- pytest: 535 pass (+3 teeth-checked) ✅
- grep `wiki/inbox` live links → ZERO (only the redirect file + a guard test that asserts it does NOT self-redirect) ✅
- team-lead Chrome-gate FULL PASS: inbox→redirect/Vault · [id] refine+back-not-404 · proposals="Nhật ký AI" audit + lùi + agent:auto + →note#110 · T4 collapse-default + expand→markdown (heading/blockquote/code/list) · console clean · nav clean · scoped CSS no global token ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ REST contract unchanged, integration tests added, module auto-discovery intact, no core/main.py edit.
- **Gate 2 (Function)**: ✅ unit tests assert observable behavior, tsc clean, vitest 100% / 0 errors, fail-closed paths explicit (reverse/accept/reject surface 4xx, no optimistic mutate), types complete.
- **Gate 3 (Sprint)**: ✅ this report written w/ verified counts; architect spot-checked full functions on disk; tester + team-lead Chrome-gate pass; counts ≥ baseline; commit format match.

## Risks / potential errors identified
- **Reverse is PARTIAL by design** — only note_create/moc have a one-step undo (soft-delete). edit/link/merge rely on manual refine (honest hint shown). This is correct for a 1-user app without a per-note version store; if the user later wants full content-undo, that's #95 (parked) — a version store, deliberately out of scope (over-engineering otherwise).
- **note#110** on the live audit-log is the BE T1 test seed (the MCP auto-apply proof), not a stray write — confirmed.
- The loading-state copy (proposals/page.tsx L347 "Đang tải proposal queue…") still says "proposal queue" — cosmetic, sub-second, low priority; can tidy in a future polish pass.

## Assumptions (user-review)
- **Reverse scope**: create/moc → soft-delete undo; edit/link/merge → manual refine (no version-undo) — *why*: no per-note version store exists (#95 parked); building one for full content-undo is over-engineering for a 1-user app — *how to change*: implement #95 version store, then wire a content-revert reverse for edit/link/merge.
- **Nav label** "Nhật ký AI" / crumb "Nhật ký AI · audit", route `/wiki/proposals` kept — *why*: clearest VN for "AI write audit-log"; keeping the route preserves deep-links/bookmarks (no redirect needed) — *how to change*: edit nav.ts label/crumb (1-line literals).
- **Vault "new note" CTA repointed to /wiki/proposals (Nhật ký AI)** — *why*: the old inbox CTA is gone and note-create-on-/wiki was never built (out of scope this sprint); the audit-log is the most relevant adjacent destination — *how to change*: build a real note-create flow on /wiki (a separate feature) and point the CTA there. **Flagged to user**: there is no in-app note-CREATE flow on /wiki today (capture is via the command bar `note …` / MCP); a dedicated create button is a future feature, not built here.
- **Audit content collapse threshold** = content >120 chars OR contains a newline → gets the collapse/markdown toggle; below that renders inline — *why*: a 1-line note doesn't need collapsing; 120 chars ≈ 2-3 lines — *how to change*: edit `isLongContent` in proposals/page.tsx.

## Commit
`feat(sprint-wiki-aifirst): AI-first wiki — gỡ inbox (redirect→Vault) · proposals→Nhật ký AI audit-log + lùi · content collapse/markdown · autonomous-default verify`
Explicit-paths only (NOT template/Life Command/* or user docs or app/projects/__tests__ pre-existing untracked).
