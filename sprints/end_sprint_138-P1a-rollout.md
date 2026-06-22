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

## Assumptions (user-review)
- **The shell serves two usages:** a WRAPPER (finance — body as children) AND a fixed-status EARLY-RETURN (portfolio — `{null}` children, status hardcoded per branch). Both byte-identical to the hand-rolled original. Screens with a `|| !data` TS-narrowing guard use the early-return form.
- **Inline-shape screens (~26) are NOT force-migrated** — wrapping them would hide a persistent header during load/error (behavior change). Honest: the rollout covers the early-return screens cleanly; the inline ones either get a narrower shell usage or stay hand-rolled (behavior-preserving > coverage).
