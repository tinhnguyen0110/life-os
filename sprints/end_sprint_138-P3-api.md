# end_sprint_138-P3-api — split lib/api.ts by domain (_client core + barrel, pure move)

> Sprint 138-P3 Task #2 (the API half — Commit 2, the LAST P3 commit). User CHỐT: split the 2 lib monoliths by domain. team-lead strict-serial: types committed+pushed (fd48dca) → this api commit → team-lead Chrome gate → push → P3 DONE → #138 complete.

## What shipped
- **lib/api.ts (1105 lines, 122 exported fns) DELETED** → **lib/api/ (18 files)**:
  - **`_client.ts`** = the shared HTTP core, verbatim: `BASE`, `class ApiError` (exported), `parseFieldsFromMessage` + `errorFromBody` (private), `apiGet/apiPost/apiPut/apiPatch/apiDelete` (exported), `export const apiBase`.
  - 16 domain files: projects, finance, market, claude, graveyard, journal, activity, brief, settings, wiki, decision, career, reminders, tracing, dev, mcp.
  - `wiki.ts` co-locates the wiki-only helpers `bumpTree` + `encodeWikiPath` + `import { markWikiTreeStale } from "@/lib/wikiTreeBus"` (all 3 were in the old api.ts — verbatim relocation, NOT new deps).
  - `index.ts` barrel = `export *` from `_client` + all 16 domain files.
- **PURE MOVE** — fn bodies byte-identical; per-fn ONLY the import lines change (helpers from `./_client`, types from `@/lib/types` barrel).
- **ZERO call-site change** across all 88 `@/lib/api` importers (barrel resolves `@/lib/api` → `lib/api/index.ts`).

## Verify (architect 4-step + independent reproduction — Rule#0, did NOT trust the report)
1. **git diff:** `D lib/api.ts` + 18 new files. lib/types UNTOUCHED (serial respected).
2. **EXPORTED-FN completeness (reproduced myself):** `git show fd48dca:frontend/lib/api.ts` exported fns sorted vs new `lib/api/*.ts` (excl barrel) sorted = **122 == 122, ZERO diff** both directions (`comm` empty). No duplicate exports.
3. **BODY-drift multiset (reproduced myself):** old vs new fn-body code-line multiset (imports + comments stripped) — the ONLY diffs are doc-comment header banners (old file-header `API client — single entry…` vs new `#138-P3: split…` / `The shared fetch wrappers…`). **Zero executable-line drift.**
4. **Pre-existing-dep check:** `markWikiTreeStale`/`wikiTreeBus` (line 6 of old api.ts) + `bumpTree`/`encodeWikiPath` — all in the old file; FE relocated verbatim to wiki.ts (relative `./wikiTreeBus` → `@/lib/wikiTreeBus` alias since the file moved one dir deeper). Not a smuggled-in dependency.
5. **tsc --noEmit exit 0** — the safety net held across all 88 importers; `_client` standalone; wiki.ts helper-hoist OK. ZERO call-site edits (git status: only `D lib/api.ts` + `?? lib/api/`).
6. **Live Chrome :3010 (architect-run, api fns power the data):**
   - /finance — REAL data: total $10,628, equity-curve $10,626, P&L −$628, allocation table (crypto 100% vs 38%), full ticker (BTC/ETH/SOL/XAU/VNINDEX/FUEVFVND). 0 console err.
   - /wiki — REAL data: 50 notes · 49 links, full EXPLORER tree (agents/Career/Memory/Mining/PKM/Principles/Projects), 6 KPI tiles, inbox/orphan/op-log/proposal-queue. Exercises getWikiTree + bumpTree + markWikiTreeStale — all working. 0 console err.
   - /tracing — REAL data: 2026-06-22 0/7 done, 7 activities (Viết nhật ký 07:00 + reminder, etc.), "⏰ Đặt giờ" pills (#139), per-card ⋯ (#136/#137), "+ Từ mẫu" (template-sets). Exercises getTracing + template-set fns. 0 console err.
   - No blank page, no Next overlay, no stale-graph error — SWC>tsc gate held.
7. **vitest 1104 (FE) — exact baseline, 0 err / 0 unhandled.**

## Deviation accepted (FE-flagged, my call)
- **A `/* ---- Decision Journal ---- */` banner traveled to wiki.ts's tail** (comment-only, at the wiki/decision boundary) — same harmless comment-relocation class as Severity in types. Appears exactly once; all decision fns present (completeness = zero diff). Accepted: byte-identical > cosmetic.

## 🔴 Operational caveat (FE-banked memory `file-to-dir-swap-needs-dev-restart`)
- Deleting `api.ts` + creating `api/` leaves `next dev`'s in-memory webpack graph stale → it serves "Failed to read source code from /app/lib/api.ts" even though tsc+vitest green + files on disk. `.next/cache` clear + touch do NOT fix; only `docker compose restart frontend` (NO --build) does. FE already restarted → container currently CLEAN (my Chrome gate ran on the restarted container, all green). **A fresh checkout on another box needs the one-time restart** — flagged so team-lead's Chrome spot-check doesn't read a false-fail.

## Gates
- Gate 2 (Function): pure refactor — NO new/removed tests (1104 baseline); tsc clean; live Chrome + console verified on 3 data-driven routes. ✓
- Gate 3 (Sprint): this doc + independently-reproduced completeness (exported-fn 122==122 + body multiset) + live Chrome real-data + count == baseline. ✓

## Assumptions (user-review)
- **`_client.ts` is the shared HTTP core; every domain api file imports from it.** parseFieldsFromMessage/errorFromBody stay private (un-exported) in _client — only ApiError + the 5 verbs + apiBase are exported. How to change: nothing — standard layering; new domain api fns import the verbs from `./_client`.
- **Barrel = zero-call-site safety net** (same as types). All 88 importers use `@/lib/api` alias → resolve unchanged.

## Commit
- Hash: (filled at commit) — `refactor(sprint-138-p3-api): split lib/api.ts by domain (_client core + barrel, pure move)`
- Files: frontend/lib/api/*.ts (NEW, 18) + frontend/lib/api.ts (DELETED) + sprints/end_sprint_138-P3-api.md.
- HOLD push for team-lead's Chrome spot-check → OK → push → **P3 DONE → #138 complete**.
