# end_sprint_138-P1a-rollout — migrate the remaining screens to <LoadErrorShell>

> Sprint 138 P1a-rollout — after the finance pilot (2ef95bb), migrate the ~29 other screens that hand-roll the `{status,errMsg}` loading/error block to the shared `<LoadErrorShell>`. Each behavior-IDENTICAL (exact copy/testids/wrapper verbatim). Per the refactor-gate: test-green + render-check pushes each batch; no per-screen Chrome gate (the pilot proved the pattern). One cumulative doc, appended per batch.

## 🔴 Scope finding (frontend, batch 1) — two screen shapes
The ~29 split into two shapes:
- **Early-return shape (like finance)** — `if(status===…) return <section>…`. CLEANLY migratable (the shell as a fixed-status early-return or a wrapper). Batch 1 = these.
- **Inline shape (~26 screens)** — loading/error rendered INLINE inside an always-present `<section>` (after a header that STAYS visible) via `&&`/ternary, NOT an early-return. Wrapping the whole body would HIDE the header during load/error = behavior change. These need either (a) the shell used to render JUST the inline hint (keeping the surrounding section/header), or (b) stay hand-rolled. → being assessed; the rollout may cover fewer than 29 cleanly (honest — not all are finance-shaped).
- **Divergent (flagged, skipped):** settings (renders `<Vtitle/>` + a section testid in its loading/error → would drop them; needs a shell `headerSlot`+`sectionTestid` extension — architect's call whether worth it).

## Batch 1 — `refactor(sprint-138-p1a-rollout-1)` (3 screens, early-return shape)
- **claude-usage** (S9): loading + error → shell; the compound `status==="error" || !data` guard kept as early-return (TS narrows `data` for the body); usage-loading/usage-error verbatim.
- **decision** (DEC): error-only branch (loading is per-section, untouched) → shell; "Không tải được decision cockpit. Kiểm tra backend ({apiBase})." + decision-error verbatim.
- **portfolio/[id]** (S6): loading + error → TWO shells (fixed-status early-returns, `{null}` children — the `|| !detail` guard needs early-return for TS narrowing); `notfound` branch left as-is (custom empty-state, not load/error); reload handler is `load` (preserved as `reload={load}`); pf-loading/pf-error verbatim.
- Verify: tsc clean; vitest FLAT 1102 (0 behavior-test delta — claude-usage 18 / decision 12 / portfolio 17 all UNCHANGED); live render-check all 3 (rendered + console clean, comments ABOVE return — the SWC gate). architect 4-step: read all 3 diffs (incl. the portfolio two-shell fixed-status pattern), byte-identical, SWC-safe.
- Commit: (filled) — `refactor(sprint-138-p1a-rollout-1)`.

## Batch 2 — `refactor(sprint-138-p1a-rollout-2)` (eea5b55) — 4 inline screens
reminders, journal, notes, portfolio(list) — the bare-hint inline usage (shell WITHOUT sectionClassName/dataScreen → bare `.hint` in-place, children={null}, body stays gated on its own `status==="ready"`). Byte-identical, vitest FLAT 1102, the 4 screens' 68 tests unchanged.

## Batch 3 — `refactor(sprint-138-p1a-rollout-3)` (035950f) — 3 inline screens
activity, brief, routines — same bare-hint usage. Byte-identical, vitest FLAT 1102, 36 tests unchanged. (Staged surgically around the in-flight padding-prop change.)

## Padding-prop batch — `refactor(sprint-138-p1a-rollout-padding)` — shell prop + 2 screens (THE END)
- **LoadErrorShell.tsx:** added `padding?: string` **default "24px 4px"** (the prior hardcoded value) + `style={{ padding }}` on both hint nodes. Backward-compat: every existing/migrated call omits it → byte-identical (the full suite proves it — all 13 callers pass unchanged).
- **projects(list) S2:** `padding="18px 16px"`, NO `reload` prop (the original error ends "…rồi thử lại." as TEXT, no button — the per-screen contract difference, handled correctly), projects-loading/projects-error verbatim.
- **market S8:** `padding="18px 16px"`, `reload={reload}` (has the "Thử lại" button), market-loading/market-error verbatim.
- Verify: full vitest 1102→1104 (+2 shell tests: default-unchanged + custom-padding-overrides-both-nodes; projects+market 26 tests unchanged = 0 behavior-delta); tsc clean; live render-check projects?tab=running + market clean, console clean (finance re-checked = the default didn't shift any existing screen).

## 🔴 Rollout CLOSED here — 13 screens migrated (don't-over-build)
Migrated: finance (pilot) + claude-usage, decision, portfolio/[id] (b1) + reminders, journal, notes, portfolio-list (b2) + activity, brief, routines (b3) + projects-list, market (padding) = **13 screens** on the shell.
LEFT hand-rolled (FLAGGED divergent — forcing them = behavior change, low reward): settings (Vtitle+section-testid in state), decision-journal (same), exchange (no-section + custom error), wiki (custom wrapper + red inline-style + empty-state), mcp-keys (skeleton loading + custom error btn), macro (custom loading skeleton), app/home (per-tile errors + a link retry). Each needs a DIFFERENT shell extension (headerSlot/sectionTestid/customLoadingNode/per-tile) — over-engineering for 7 screens. The shell dedups the clean 13; the divergent tail stays as-is. P1a DONE.

## Assumptions (user-review)
- **The shell serves two usages:** a WRAPPER (finance — body as children) AND a fixed-status EARLY-RETURN (portfolio — `{null}` children, status hardcoded per branch). Both byte-identical to the hand-rolled original. Screens with a `|| !data` TS-narrowing guard use the early-return form.
- **Inline-shape screens (~26) are NOT force-migrated** — wrapping them would hide a persistent header during load/error (behavior change). Honest: the rollout covers the early-return screens cleanly; the inline ones either get a narrower shell usage or stay hand-rolled (behavior-preserving > coverage).
