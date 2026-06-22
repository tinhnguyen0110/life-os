# end_sprint_138-P1a-loaderrorshell — shared <LoadErrorShell> + finance pilot (FE refactor)

> Sprint 138 (FE-refactor) Phase 1a — the PILOT. 30 screens hand-roll the SAME-shaped `{status,errMsg}` loading/error block (divergent copy). This extracts a shared `<LoadErrorShell>` + migrates ONE screen (finance) behavior-IDENTICAL, to prove the pattern before the 29-screen rollout. Behavior-preserving, test-gated, one commit. (The original P1a "ConfirmModal consolidation" was deferred — the confirm patterns are heterogeneous, not a clean win.)

## What shipped (1 migrated + 2 new)
- **components/LoadErrorShell.tsx (NEW):** `<LoadErrorShell status loadingLabel errorLabel reload? reloadLabel? loadingTestid? errorTestid? sectionClassName? dataScreen? children>` — `loading`→a `.hint` div (screen's exact label + testid); `error`→a `.hint neg` div (screen's exact label, which interpolates its own {errMsg}/apiBase) + a reload button when `reload` given; else→children. Optional `<section className data-screen>` wrapper reproduces a screen's existing wrapper. Labels are ReactNode so wording is preserved verbatim.
- **app/finance/page.tsx (migrated, net -8 lines):** the two hand-rolled `if (status===…) return <section>…` blocks → ONE `<LoadErrorShell>` wrapping the body, passing the EXACT copy/testids/wrapper (sectionClassName="view", dataScreen="S5", finance-loading/finance-error, "Đang tải tài chính…", "Không tải được tài chính: {errMsg}. Kiểm tra backend ({apiBase}).", "Thử lại"). Body `<section data-testid="finance-screen">` unchanged (now children). ZERO copy/layout/testid change.
- **components/__tests__/LoadErrorShell.test.tsx (NEW):** 7 unit tests (loading→label / error→label+reload / error-without-reload→no-btn / custom-reloadLabel / ready→children / section-wrapper / node-errorLabel-interpolation).

## 🔴 A live-only regression caught (the SWC>tsc lesson)
frontend's first migration put a `//` between `return (` and the JSX. **tsc clean + vitest green, but Next's SWC threw "Unexpected token. Expected jsx identifier" + blanked the page** — caught only via the live Chrome console. Fixed (comment moved above `return`). → architect memory `swc-stricter-than-tsc-live-console-gate`: for a Next/SWC FE, the live Chrome console (+ a real render) is the authoritative compile gate, not tsc+vitest. (Reinforces the refactor-gate's Chrome spot-check.)

## Verify (architect 4-step + live Chrome)
- **Read full functions:** LoadErrorShell (behavior-preserving by design) + the finance migration (byte-identical — exact copy/testids/wrapper; SWC comment placement fixed). On top of the pushed fc9f9ee, no lane churn.
- **Live Chrome (architect, :3010):** /finance renders IDENTICALLY — title "Tài chính"/sub/KPIs/equity-curve ($10,626)/allocation-table, `<section data-screen="S5">`; console CLEAN, no Next overlay (rules out the SWC gotcha). ✓
- **vitest 1102/0err** (1095 + 7 new shell tests). 🔴 **finance's 15 existing tests pass UNCHANGED** — the behavior-identical proof (0 behavior-test delta). tsc clean.

## Gates
- Gate 2 (Function): the new component has unit tests (7, behavior); the migration adds ZERO behavior tests (byte-identical); finance's tests pass unchanged; tsc clean; live Chrome + console verified. ✓
- Gate 3 (Sprint): this doc + spot-checked full functions + live Chrome + count grew only by new-component tests (1095→1102, finance 0-delta). ✓

## Assumptions (user-review)
- **Refactor approach: pilot-first.** Migrate ONE screen (finance) to prove the shell, then roll out the other 29 one-per-commit. Why: de-risk a 30-screen change (behavior-preserving is silent-regression-prone). How to change: batch more per commit if the pilot is clean + the user prefers speed (but one-per-commit is the safe default).
- **Behavior-preserving = byte-identical.** Each migration passes the screen's EXACT existing copy/testids; the shared shell renders the same markup. No copy/layout change anywhere.

## Commit
- Hash: (filled at commit) — `refactor(sprint-138-p1a): shared <LoadErrorShell> + finance pilot (behavior-identical)`
- Files: frontend/components/LoadErrorShell.tsx (NEW) + frontend/components/__tests__/LoadErrorShell.test.tsx (NEW) + frontend/app/finance/page.tsx (migrated) + this doc.
- FE refactor — on top of fc9f9ee. Per the refactor-gate: test-green + a UI-render step → flag team-lead for a finance Chrome spot-check → push on their OK (lighter than a full pre-push hold).
