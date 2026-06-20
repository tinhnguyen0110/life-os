# End Sprint SIDEBAR-UX — privacy (hide+pass) + pin (backend) + collapse/groups UX (Task #72/#74)

> Status: **REVIEWED — 3 gates green, committing.** Task #72 + the #74 adjust (5 UX changes). The #1 collapse-button bug was team-lead's quick-fix (folded in). The sprint scope evolved heavily mid-flight (5 changes + 2 persist-split flip-flops + 2 premature "done"s) — the final shipped set is clean.

## What shipped (5 changes, BE+FE, one commit)
1. **Privacy money-mask = HIDE (••••) + pass-modal reveal** (reworked from blur — user "đau mắt"). `[data-privacy="on"] [data-amount]` → real value `visibility:hidden` + `::after content:"••••"` (display-only mask, NOT blur; the API value is untouched). Reveal = `PrivacyRevealModal` → `verifyPrivacyPass(pass)` → `POST /settings/privacy/verify` → on `{ok:true}` unlock. **The pass is env-only (`LIFEOS_PRIVACY_PASS`, default "0110"), compared server-side via `hmac.compare_digest` (constant-time), NEVER serialized to the FE** (grep "0110" in frontend/ = empty). `unlocked` = session-only (not persisted — an unlock shouldn't sync). `body[data-privacy]` = `privacy && !unlocked`.
2. **Collapse header icon-only** — when `#app.collapsed`, `.sb-logo` + `.sb-word` hidden; the `.sb-collapse` chevron is the ONLY survivor (team-lead's bugfix keeps it visible to re-expand — NOT re-hidden).
3. **Privacy eye button → TopBar** (right cluster, from the sidebar header). Works app-wide because `usePrivacy` broadcasts on the `lifeos:privacy` CustomEvent + sets the `body[data-privacy]` attr — so the button's location is independent of the blur/hide mechanism.
4. **Collapsible nav GROUPS, default-collapsed** — section headers are toggles; `lifeos.navgroups` localStorage; the active route's group + "📌 Ghim" auto-expand (computed, not persisted, so the user is never lost). Active detection is longest-prefix (`pathname.startsWith(route+"/")` → `/portfolio/[id]` opens TÀI CHÍNH). Whole-sidebar-collapse forces all open (no conflict).
5. **Backend privacy-verify endpoint** — `core/config.py privacy_pass` (env) + `POST /settings/privacy/verify {pass} → {ok}` (`# public + unlimited because single-user localhost veil`). No AppConfig field, no hash, no DB, no sync — env-string compare via hmac.compare_digest.
- **Pin/Favorite (the original #72-B, unchanged):** `pinnedRoutes: list[str]` on AppConfig (BACKEND/settings, multi-device sync); `usePins` reads `config.pinnedRoutes` + pin/unpin = `save({pinnedRoutes:[...]})` (full-list replace PATCH, fail-closed, ADD-not-move, fail-soft on unknown routes). A "📌 Ghim" group at the top.

### Verified counts (architect re-ran independently — Rule #0)
- **vitest: 843 passed (843), 77 files, 0 errors** (was 837 pre-#74 FE; +the privacy-modal/nav-group/pin tests). **Backend: 1651 passed** (1646 #72 pinnedRoutes + 5 privacy-verify). tsc + mypy clean.
- **MY disk pre-check of the 3 change-5 gates (the exact things missing the prior round):** (1) endpoint WIRED — `verifyPrivacyPass` (api.ts:401) CALLED at usePrivacy.ts:122 (real call-site, not built-but-not-wired); (2) HIDE-not-blur (••••, no `filter:blur` on money); (3) pass NOT in FE source (grep "0110" empty). All PASS.
- **team-lead LIVE Chrome-verified the change-5 state machine:** OFF→$10,626 shown; eye→ON+locked→TỔNG TÀI SẢN/P&L = •••• ("+$0" stays sharp, selective); eye→modal; type 0110→submit→unlock→money back (real backend round-trip); wrong→stays ••••. + 3 (eye on TopBar) + 4 (groups default-collapsed) confirmed.

## Code review (architect — 4-step, the change-5 wiring + pin-backend + collapse-bugfix hardest)
1. **git status/diff** — files STABLE (newest mtime 20:45, reviewed 20:50). The INCLUDE set (below) + the EXCLUDEs (docker-compose/.env.local/.env/template/data) verified absent from `--cached`.
2. **Read full functions** — usePrivacy (localStorage mode + session-only unlocked + broadcast + body-attr); usePins (config.pinnedRoutes via useSettings, full-list PATCH, fail-soft resolve); useNavGroupCollapse (default-collapsed + active/Ghim auto-open); the verify endpoint (hmac.compare_digest, env-only); the hide CSS + collapse-bugfix.
3. **Verify against plan + the change-5 flags + the locked split** — all present.
4. **Hunt additional issues — verified:**
   - **🔑 change-5 #1 (built-but-not-wired):** the verify endpoint has a REAL FE call-site (usePrivacy:122 → verifyPrivacyPass → POST). The prior round's gap (dead endpoint) is CLOSED. The modal POSTs, unlocks on ok. ✅
   - **🔑 change-5 #2 (pass not in bundle):** grep "0110" in frontend/ = empty; the compare is server-side. ✅
   - **🚫 veil not over-engineered:** env-string compare (hmac constant-time, the CORRECT way — not gold-plating), no hash/JWT/rate-limit/sync, `# localhost veil` comment. ✅
   - **pin BACKEND round-trip:** the test asserts `patchSettings` called with `{pinnedRoutes:["/finance"]}` + UI trusts the server config (fail-closed) → Ghim shows it. Real round-trip, not the hook. ✅
   - **collapse-bugfix intact:** `.sb-collapse` NOT in the `#app.collapsed display:none` list (only logo+word added); the comment confirms "the chevron is the ONLY survivor." ✅
   - **change-4 sub-route:** `isActive` longest-prefix → /portfolio/[id] opens TÀI CHÍNH. ✅
   - **persist split (locked):** privacy mode = localStorage (device-local); unlocked = session-only; pinnedRoutes = backend. Two paths intentional. ✅

## Assumptions (user-review)
- **privacy mode on/off = localStorage** (device-local "someone's watching THIS device"); **the reveal-pass = env (`LIFEOS_PRIVACY_PASS`, default 0110), verified server-side** (`POST /settings/privacy/verify`, hmac.compare_digest); **unlocked = session-only** (not persisted/synced). **Why:** a privacy veil is per-device + per-moment; the pass is a localhost cosmetic gate, NOT auth (user: "lưu ở env cũng được, đừng overengineering"). **How to change:** `LIFEOS_PRIVACY_PASS` env / the usePrivacy persist.
- **privacy HIDES money (••••), does NOT hide tabs** (user reverted the hide-finance-group). Every screen stays visible; only `[data-amount]` money is masked (display-only, real value on unlock). **How to change:** the `data-amount` tag set / the hide CSS.
- **pinnedRoutes = BACKEND/settings** (multi-device sync, Tailscale); full-list replace PATCH, ADD-not-move, fail-soft. **Why:** pins are user content prefs that should sync. **How to change:** usePins / the AppConfig field.
- **nav-group collapse = localStorage, DEFAULT-collapsed**; active group + Ghim auto-open. **Why:** device-local display pref (how a screen LOOKS here, not WHAT syncs); default-collapsed is the user's ask, made safe by the auto-open. **How to change:** the default in useNavGroupCollapse / `lifeos.navgroups`.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ `POST /settings/privacy/verify` ({ok}, no auth/limit by design — localhost veil) · ☑ `pinnedRoutes` on AppConfig/Patch (round-trips, []-clears) · ☑ no privacy AppConfig field (env-only) · ☑ NEUTRAL · ☑ pass never serialized. **PASS**
- **Gate 2 — Function:** ☑ change-5 endpoint WIRED (real call-site) · ☑ hide-not-blur · ☑ pass-not-in-bundle · ☑ veil-not-over-built (hmac, no gold-plating) · ☑ pin backend round-trip (real PATCH) · ☑ collapse-bugfix intact · ☑ change-4 sub-route + auto-open · ☑ persist split (privacy-local/unlocked-session/pin-backend) · ☑ vitest 843 + pytest 1651, 0 errors · ☑ tsc/mypy clean · ☑ Chrome self-verify (team-lead ran the state machine live). **PASS**
- **Gate 3 — Sprint:** ☑ end doc + verified counts + the live state machine · ☑ architect spot-checked full functions + the 3 change-5 gates on disk · ☑ counts ≥ baseline · ☑ team-lead LIVE Chrome-verified all 5 · ☑ assumptions logged (4) · ☑ commit format. **PASS**

## Risks / follow-ups
- **The privacy pass is a localhost cosmetic veil, NOT security** — env-stored, no auth/rate-limit; anyone with shell access reads the env. That's BY DESIGN (single-user, "đừng overengineering"). Documented so it's never mistaken for access control.
- **The sprint churned hard** (5 changes + 2 persist-split flip-flops + 2 premature "done"s) — the disciplines that held: the locked persist-split (privacy-local/pin-backend, re-confirmed after each flip), the built-but-not-wired gate on change-5 (caught the dead endpoint the prior round), and holding the commit for team-lead's live re-verify (never committed a 2-of-4 / still-blur / dead-endpoint tree).
- **EXCLUDED (team-lead's PA1 infra, owned separately):** docker-compose.yml + frontend/.env.local + backend/.env (the Tailscale IP + the pass env) — NOT in this commit.
- Process note: my one AskUserQuestion slip (the docker-compose scope call) is on record — route decisions to team-lead, never the banned tool. The outcome was right, the route was wrong.
