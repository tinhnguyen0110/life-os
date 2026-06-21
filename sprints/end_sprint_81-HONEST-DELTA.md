# end_sprint_81-HONEST-DELTA — one shared deltaGlyph across all 4 delta widgets (Cairn #81)

> Result. The honest 3-way delta rule (flat/$0 → neutral ▬, null → ▬, real → ▼/▲) was only in the home tile (#72-FE); the dogfood found the other 3 delta widgets still drifted. Consolidated to ONE shared `deltaGlyph(v)` helper (lib/format.ts) applied to all 4 (Home + NetWorth + EquityCurve + MarketChart) → can't drift per-widget again. Commit `<hash>` `fix(sprint-81-honest-delta)`. Status: ✅ verified (FE agent + architect 4-step + team-lead Chrome). frontend-w3-2 BUILT; architect committed (§3, FE-domain). A dogfood→fix lane (post-roadmap, the gap-finder generating real value).

## What shipped (11 FE files)
| File | Change |
|---|---|
| `lib/format.ts` | NEW `deltaGlyph(v: number|null|undefined) → {arrow, cls}` — the ONE 3-way rule: <0→▼/neg, >0→▲/pos, ===0 (FLAT)→▬/faint (NOT a green ▲), null/NaN→▬/faint (NO fabricated arrow/color). Documented. The single source of the honest-delta truth. |
| `app/page.tsx` | Home refactored to COMPOSE deltaGlyph (behavior-identical — the #72-FE dayDelta logic now delegates to the shared helper). |
| `app/finance/page.tsx` (NetWorth) + `components/EquityCurve.tsx` + `components/MarketChart.tsx` | the 3 widgets that still drifted → now compose deltaGlyph (get the honest rule). |
| `lib/tokens.css` | the neutral tone reuses the existing `.faint` (no new token). |
| 5 test files (format + finance + home + EquityCurve + MarketChart) | +11 tests — the teeth. |

## Design (LOCKED — one helper, no per-widget drift)
- ONE `deltaGlyph` = the honest-delta rule's single home. All 4 delta widgets COMPOSE it (not their own copy) → a future change is one-place, can't drift per-widget (the exact failure the dogfood found: #72-FE fixed home but the other 3 stayed 2-way). The neutral = the existing `.faint` (tone-less), no new token.

## Verification (FE agent + architect 4-step + team-lead Chrome)
- **frontend-w3-2:** teeth PROVEN — reverted deltaGlyph to 2-way → exactly 9 tests RED across all 4 widgets + core (real loss/gain stayed green — surgical teeth, not over-broad). +11 tests, vitest 911/0/0, tsc clean.
- **architect 4-step (read full):** deltaGlyph = the documented 3-way (flat≠gain, null≠fabricated) ✅; all 4 widgets compose it (grep confirms — no per-widget copy) ✅; Home refactor behavior-identical (delegates the #72 logic) ✅; FE-only surface (11 files), NO #79 BE leak (the dirty conftest/test_suite_isolation are #79's — staged OUT) ✅; my re-run format+4-widgets 86/0, tsc clean.
- **team-lead Chrome (all 4):** NetWorth ▬-on-null, EquityCurve ▬-on-0.00%, MarketChart ▼-on-real(-0.06%) [the distinguishing: NO over-correction of a real change], Home UNCHANGED (regression). Console clean.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest 911/0 + tsc clean + the teeth (9-RED-on-revert, surgical) + Chrome all 4 (incl. the no-over-correction distinguishing). ✅
- **Gate 3 (Sprint):** end-doc; FE-agent + architect 4-step + team-lead Chrome; commit-hygiene (11 FE files, content-diffed vs the intermixed #79 BE — staged FE-only, no leak); commit format. ✅

## Assumptions (user-review)
- ONE shared deltaGlyph for all delta widgets (Home/NetWorth/EquityCurve/MarketChart) — flat→▬, null→▬, real→▼/▲. The honest-delta rule lives in one place (no per-widget drift). **How to change:** deltaGlyph in lib/format.ts (one edit → all 4).

## Notes
- Cairn #81. A DOGFOOD→FIX lane (post-roadmap): the FE dogfood found the #72-FE honest-delta rule didn't propagate to the other 3 delta widgets → consolidated to one helper (the no-future-drift fix) + teeth-proven. The gap-finder generating real value now the standing roadmap is delivered. frontend-w3-2 BUILT; architect committed (§3). Committed from an intermixed tree (#79 BE building) — surgical FE-only stage. Next: #79 (BE, when DONE) + #78 + #64-P3 + more dogfood/user-direction.
