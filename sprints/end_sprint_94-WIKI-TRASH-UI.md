# end_sprint_94-WIKI-TRASH-UI — wiki trash/restore/bulk UI (Cairn #94 FE, CLOSES #94)

> Result. The "xoá nhầm → rollback" recovery UI: a 🗑 Trash modal (GET /wiki/trash) listing soft-deleted notes with a Restore button (POST /restore → back in the vault), bulk-select + bulk soft-delete (in-page confirm), and the note-detail delete changed to SOFT ("Chuyển vào thùng rác?" → recoverable, not a scary permanent delete). Commit `<hash>` `feat(sprint-94-wiki-trash-ui): trash/restore/bulk UI — xoá-nhầm rollback (#94 FE, closes #94)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + the in-page-confirm/restore reads + INDEPENDENT live restore round-trip + tsc + vitest). Cairn #94 FE — CLOSES #94 (BE f5fa56f + this FE). The LAST task of the wiki user-pain batch.

## What shipped (FE — trash modal + hook + soft-delete affordance)
| File | Change |
|---|---|
| `components/WikiTrash.tsx` (NEW) | the recovery surface: lists GET /wiki/trash (title or honest "(không có tiêu đề)" for empty-title · when-deleted · folder) with a per-row Restore button (fail-closed, per-row error); honest empty-state ("Thùng rác trống"); loading skeleton; render-only. |
| `lib/useWikiTrash.ts` (NEW) | list (alive-guard, validates Array.isArray(d.trash), honest-empty count 0) + restore (fail-closed throw→caller + refetch-after-restore). |
| `app/wiki/[id]/page.tsx` | the note-detail delete is now SOFT: "Chuyển vào thùng rác?" → `await remove()` (soft DELETE) → `router.push("/wiki?trashed=${id}")` (a recoverable signal, NOT a scary permanent delete + a hard router.push("/wiki")). |
| `app/wiki/page.tsx` | the 🗑 Trash modal trigger + the "moved to trash · restore" toast (from `?trashed=<id>`) + bulk-select mode (selectedIds Set) → bulk soft-delete via `bulkDeleteWikiNotes` with an IN-PAGE confirm (bulkConfirm state + bulk-confirm-yes/no — NOT window.confirm) + per-id fail-soft results. |
| `lib/api.ts` | getWikiTrash / restoreWikiNote / bulkDeleteWikiNotes (the FROZEN #94-BE endpoints); deleteWikiNote now hits the soft DELETE. |
| `lib/types.ts` | WikiTrashItem + WikiNote += deletedAt + the bulk-result shape. |
| `lib/tokens.css` | the .wtrash-* styles. |
| tests | `components/__tests__/WikiTrash.test.tsx` (NEW) + vault/note tests updated (the soft-delete + bulk + trash flow). |

## Design (LOCKED — recoverable affordance, in-page confirm, render-only)
- **the recovery flow (the user's pain "xoá nhầm"):** delete → SOFT ("Chuyển vào thùng rác?" / "moved to trash" toast) → open Trash → Restore → back in the vault. No scary permanent-delete from the FE.
- **in-page confirm (NOT window.confirm):** both the note-detail soft-delete + the bulk-delete use in-page UI (the browser-automation note: a JS dialog blocks the Chrome extension).
- **render-only / honest:** the BE owns the soft-delete store + the trash list; the FE displays + triggers restore/bulk. Honest empty-trash, honest no-title ("(không có tiêu đề)"), honest BE-down/malformed error states. fail-closed restore/bulk.
- **bulk fail-soft:** per-id results (a bad id → its error row, the rest soft-delete).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** WikiTrash (list/restore/empty/error, fail-closed) ✅; useWikiTrash (alive-guard, validates trash array, fail-closed restore + refetch) ✅; note-detail delete now SOFT (→ ?trashed, no hard router.push) ✅; vault bulk uses in-page confirm (bulk-confirm-yes/no, NO window.confirm) + the moved-to-trash toast ✅; FE-only surface (the #51-BE reminders files NOT in this — staged OUT) ✅.
- **architect INDEPENDENT live restore round-trip (the load-bearing recovery — the BE flow the FE drives):** create → soft-delete → /wiki/trash count 13→14 (in trash) → restore → gone-from-trash, deletedAt=None, title intact → cleanup. The "xoá nhầm" rollback works end-to-end. ✅
- **architect independent re-run:** tsc clean (exit 0); vitest FULL **86 files / 991 passed / 0 failed** (980→991, +11 WikiTrash + vault/note updates); the FE-#94 targeted run = 30 passed.
- **frontend-w3-2 Chrome:** trash modal lists 13 soft-deleted; restore #65 round-trip (trash 13→12→back); bulk-select with in-page confirm (window.confirm spy NOT called); soft-delete toast; the note-detail delete = soft ("Chuyển vào thùng rác?" → recoverable). dark-mode; console clean.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest (WikiTrash list/restore/empty/error + bulk + soft-delete) + tsc clean + the in-page-confirm (no JS dialog) + the independent live restore round-trip + Chrome. ✅
- **Gate 3 (Sprint):** end-doc; FE-agent Chrome + architect 4-step + independent live; commit-hygiene (FE-only — the #51-BE files staged OUT, no leak); commit format. ✅

## Assumptions (user-review)
- delete is SOFT (recoverable via Trash → Restore); NO hard-delete/purge from the FE this sprint. **How to change:** add a purge-UI (gated) if the user wants permanent delete.
- bulk + note-detail delete use IN-PAGE confirm (not JS dialog). **How to change:** the confirm UI in page.tsx.

## Notes
- Cairn #94 FE — **CLOSES #94** (BE f5fa56f soft-delete/restore/bulk/MCP + this FE trash/restore/bulk UI). The "xoá nhầm" rollback is end-to-end: delete → trash → restore. frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). Committed from an intermixed tree (#51-BE was in flight, now landed 750f281) — FE-only surgical stage, no leak.
- 🔴 **#96 (queued, HIGH — a recheck-all-consumers miss #94 exposed):** the #94 deletedAt hide-points covered tree/search/all_notes/count_by_status but NOT `recentActivity` → soft-deleted junk leaks into daily_brief.wikiContext.recentNotes (the #36 brief consumer; dup-noteId + empty-title). team-lead diagnosed it on the container (13 trash notes leaking). The #96 fix = exclude deletedAt from recentActivity + dedup by noteId. NOT a purge (the 13 trash notes are correctly soft-deleted). Logged for the next batch.
- The wiki user-pain batch (#93/#94/#97/#51) is now COMPLETE with this commit.
