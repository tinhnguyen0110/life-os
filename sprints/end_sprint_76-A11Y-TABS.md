# end_sprint_76-A11Y-TABS — keyboard-accessible tab chips (Cairn #76)

> Result. The filter-tab chips were `<span role="button" tabIndex={0}>` (mouse + manual-tabindex, no native keyboard semantics) → converted to real `<button type="button">` across the screens + a `:focus-visible` ring. A FE-found a11y gap (frontend's own dogfood). Commit `<hash>` `fix(sprint-76-a11y-tabs)`. Status: ✅ verified (FE agent). frontend-w3-2 BUILT; architect committed (§3, FE-domain commit-hygiene). Reactive sprint.

## What shipped (10 FE files)
| File | Change |
|---|---|
| `app/{activity,career,exchange,journal,notes,portfolio,reminders}/page.tsx` + `components/MarketOverview.tsx` | filter-tab chips `<span role="button" tabIndex={0}>` → `<button type="button">` (native keyboard + focus + Enter/Space, no manual tabindex). data-testid + class preserved (pixel-identical via the tokens.css tweak). |
| `lib/tokens.css` | `.tab` works on `<button>` (margin:0 + line-height:inherit → pixel-identical to the old span) + `.tab:focus-visible { outline }` (keyboard-visible focus ring; mouse-click keeps no ring via :focus-visible). |
| `app/reminders/__tests__/reminders.test.tsx` | adapted for the button semantics. |

## Design (LOCKED — native semantics over ARIA-retrofit)
- A real `<button>` gives keyboard focus + Enter/Space activation + the right role natively — strictly better than `span[role=button][tabIndex=0]` (which needs manual key handlers for full a11y). `:focus-visible` shows the ring only for keyboard users (not mouse-click). Pixel-identical look (the tokens.css reset).

## Verification (FE agent + architect commit-hygiene)
- **frontend-w3-2:** vitest green (the a11y test goes RED if reverted to span), tsc clean, Chrome (tab keyboard-focusable + Enter activates + focus ring visible on keyboard nav).
- **architect commit-hygiene (Rule#0):** content-diffed each of the 10 files = ONLY the span→button + focus-visible a11y change (no #63-P3 dev-activity content — the FE lanes are cleanly file-split: #76 = pages + tokens.css; #63-P3 = nav/api/types + the new dev-activity files); explicit-staged 10 #76 files; #63-P3's nav.ts/api.ts/types.ts stay dirty (NOT swept).

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest green (RED-on-revert) + tsc clean + Chrome keyboard verify. ✅
- **Gate 3 (Sprint):** end-doc; FE-agent verified; commit-hygiene (10 explicit #76 files, content-diffed vs #63-P3, no leak); commit format. ✅

## Assumptions (user-review)
- tab chips = real `<button>` (native keyboard a11y) + `:focus-visible` ring, pixel-identical look. **How to change:** the tab component / tokens.css.

## Notes
- Cairn #76. frontend's own dogfood a11y finding. frontend-w3-2 BUILT; architect committed (§3). Dropped mid-build for #63-P3 (P3 > #76), resumed + completed to a clean state, committed in arrival-order (#63-P1 → #76 → #63-P3). The FE lanes are cleanly file-split so no shared-file tangle.
