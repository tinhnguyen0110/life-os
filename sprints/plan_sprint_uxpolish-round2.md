# plan_sprint_uxpolish-round2 — DISPATCH-READY (HELD, do NOT dispatch until user OKs round-2)

> Prepared by architect per team-lead steer (a): refine the DRAFT into a dispatch-ready plan ONCE, then stand by. NO dispatch, NO build. Evidence gathered live from tokens.css on origin 21cca96 (2026-06-23).
> Two tasks: **A1 row-hover unify** (real drift, low-risk, ready) + **C1 focus-visible a11y** (real gap, BUT honest scope caveat below — bigger than CSS).

---

## Honest-scope gate (read first)
Round-1 did per-screen objective passes; the app is genuinely polished. Round-2 proceeds ONLY if the user wants it. These two are the highest-value remaining, evidence-grounded. A1 is a clean win. C1 has a scope caveat the user should see before committing.

---

## Task A1 — Row-hover treatment unification (READY — low-risk)

### Context
Every clickable row/card got a hover in round-1, but the *treatment* drifted into 3 row-idioms with no clear rule. A holistic sweep to ONE canonical row-hover makes the app feel like one system. (Cards are already nearly uniform — see OUT.)

### Evidence — the 3 row-hover idioms today (tokens.css, origin 21cca96)
**Idiom 1 — `background:var(--bg-2)` (solid) — 11 list-rows:**
`.feed-row`:417 · `.sbc-row`:561 · `.woutlink.clickable`:639 · `.wbl-row.clickable`:653 · `.winbox-row`:676 · `.wsearch-row`:715 · `.wlist-row.clickable`:731 · `.wex-folder-head`:834 · `.wex-file`:852 · `.fin-alloc-row`:959 · `.news-digest-row`:1066

**Idiom 2 — `color-mix(in oklch, var(--bg-2) 55%, transparent)` (subtle) — 3 rows:**
`.rem-row`:390 (guarded `:not(.overdue):not(.done)`) · `.set-row`:589 (guarded `:not([data-enabled="0"])`) · `.exch-bal-row`:965
(+ `.scope-tool-wrap`:1232 at 60% — mcp-keys internal, leave)

**Idiom 3 — `background:var(--bg-1)` (darker) — 4 TABLE-rows:**
`.mov-table tbody tr`:998 · `.dev-repo-table tbody tr`:1170 · `.proj-table tbody tr`:1181 · `.wtrash-row`:1203

### Decision (architect — decide-and-log)
- **Canonical LIST-row hover = `background:color-mix(in oklch, var(--bg-2) 55%, transparent)`** (idiom 2, the subtle variant). Rationale: subtle reads better on a dense dark UI than the heavier solid bg-2; it's already the "considered" choice on rem/set/exch. → migrate the 11 idiom-1 list-rows to idiom 2.
- **TABLE-rows (idiom 3, bg-1) STAY** as their own family. A `<table>` row hover is a distinct surface from a list `<div>` row; bg-1 (darker, full-bleed) is the correct table convention and is already internally consistent across all 4 tables. Forcing them to the list idiom would look wrong. → LEAVE.
- **Preserve all existing guards** (`:not(.overdue)` etc.) when editing the guarded rows (don't touch them — they're already idiom 2).

### Scope IN
- tokens.css: change the 11 idiom-1 list-row `:hover` rules' `background:var(--bg-2)` → `background:color-mix(in oklch, var(--bg-2) 55%, transparent)`. Exact lines listed above.
### Scope OUT
- TABLE-rows (998/1170/1181/1203) — leave (separate family, already consistent).
- Card hovers (`.note-card`:466 / `.routine-card`:438 / `.macro-card`:1035 / `.wprop-card`:781 / `.act-card`:1094) — already uniform on `border-color:var(--line-2)`; minor bg-2-add variance is acceptable, NOT in scope (honest: not a real drift).
- Button/tab/chip/icon hovers — separate already-fine family, OUT.
- `.scope-tool-wrap`:1232 (mcp-keys internal 60%) — leave.
- NO new classes, NO JSX change, NO global-token change.

### Verify-criteria
1. The 11 listed list-rows render the subtle 55% hover; the 3 already-subtle rows unchanged; the 4 table-rows unchanged.
2. `./node_modules/.bin/vitest run` green (no count change — pure CSS value swap).
3. Live Chrome: hover a feed-row, a wiki list-row, a fin-alloc-row, a news-digest-row → all show the same subtle tint; a proj-table row still shows bg-1; console clean.
4. tokens.css diff = ONLY the 11 listed `:hover` background values changed; grep no other selector touched.

### Risk: LOW (scoped `:hover` value swaps, behavior-preserving, no JSX).

---

## Task C1 — focus-visible a11y (READY-as-CSS, but HONEST scope caveat)

### Context
Keyboard-nav focus indicators are sparse: only **1** `:focus-visible` rule app-wide (`.tab`:291). mcp-keys-v2 did NOT add focus-visible (its interactive bits are buttons/inputs with browser-default focus). A consistent focus-ring pass is a genuine a11y improvement.

### ⚠️ Honest scope caveat (user must see before OK)
Most clickable rows are plain `<div onClick>`, NOT `<button>`/`<a>`/`tabIndex` — only **7** elements app-wide have `tabIndex`/`role="button"`. A plain `<div>` **cannot receive keyboard focus**, so a `:focus-visible` CSS rule on it never fires. So C1 splits into two honestly-different efforts:
- **C1a (CSS-only, small):** add a canonical `:focus-visible` outline to the elements that ARE already focusable — native `<button>`, `<a>`, `<input>`, `.tab` (done), and the 7 tabIndex/role=button elements. Low-risk, real value for keyboard+button users.
- **C1b (JSX, larger — NOT a quick pass):** make clickable `<div onClick>` rows keyboard-operable (add `tabIndex={0}` + `role="button"` + onKeyDown Enter/Space) THEN ring them. This is a real a11y feature across ~28 row/card families — a multi-file FE effort, NOT a CSS sweep. Should be its own sprint if wanted.

### Recommendation
- If the user wants "a quick a11y polish" → do **C1a only** (CSS focus-ring on already-focusable elements). Defer C1b.
- If the user wants "full keyboard nav" → that's a dedicated sprint (C1b), scope it separately. Do NOT bundle into round-2 polish.

### Scope IN (C1a only)
- tokens.css: one canonical `:focus-visible` rule applied to `button`, `a`, `input`, `select`, `textarea` within app surfaces + the 7 tabIndex/role=button elements: `outline:2px solid var(--accent); outline-offset:1px;` (matching the existing `.tab` convention line 291). Use `:focus-visible` (not `:focus`) so mouse-click shows no ring.
### Scope OUT (C1a)
- Do NOT add tabIndex/role/onKeyDown to divs (that's C1b, separate sprint).
- Do NOT touch the existing `.tab:focus-visible` (already correct).

### Verify-criteria (C1a)
1. Tab-key through the app → buttons/links/inputs/tabs show a consistent accent outline; mouse-click shows none.
2. vitest green; tsc clean.
3. Live Chrome keyboard-tab walk of 2-3 screens → visible rings on focusable elements, console clean.

### Risk: C1a LOW (scoped focus-visible CSS). C1b NOT in this plan (flagged as separate sprint).

---

## Dispatch ordering (WHEN user OKs — not now)
- A1 + C1a are independent (both tokens.css, but disjoint rule-sets) → could be ONE fe task (one commit) or two. Recommend ONE combined fe dispatch (both are small scoped CSS, same file, same theme) → one `fix(sprint-uxpolish-round2)` commit, hunk-split if needed. A1's 11 rows + C1a's focus block are non-overlapping lines.
- C1b (keyboard-operable divs) → DEFER; propose as its own a11y sprint only if user wants full keyboard nav.

## Status: HELD. Prepped once per team-lead steer. Awaiting user round-2 OK. No further prep, no dispatch.
