# Sprint SIDEBAR-UX — privacy toggle + pin/favorite routes (persist backend) (Task #72)

User's 3 asks: #1 collapse-button bug (FIXED by team-lead, CSS quick-fix, live-verified). Remaining: (A) Privacy toggle — blur amounts (••••) + hide the finance group; (B) Pin/Favorite routes → a "Ghim" group at the top, PERSIST BACKEND (settings, NOT localStorage — multi-device sync via Tailscale). BE (AppConfig fields) + FE (sidebar UI + the prefs).

## Kickoff — 2026-06-20 (§3.3a — patterns confirmed, shapes decided)

### Backend pattern (the wikiAgentAutonomous template — exact)
- `AppConfig` (settings/schema.py): a typed field with a default. `AppConfigPatch`: mirror as `<type> | None = None`.
- `settings/service.py`: PATCH = `patch.model_dump(exclude_none=True)` → merge → `md_store.write_file` (fail-CLOSED, one git commit). `_render` = `yaml.safe_dump(config.model_dump())` — **handles a `list[str]` natively** (pinnedRoutes round-trips through YAML, no special casing). `exclude_none` means a `None` patch field = no change; to CLEAR pins the FE sends `pinnedRoutes: []` (empty list, not None) → persists.

### FE pattern + THE KEY DISTINCTION (backend vs localStorage)
- **Existing** sidebar hide/reorder prefs = **localStorage** (`sidebar-prefs.ts`, STORAGE_KEY "lifeos.sidebar", "pure client-side, no backend"). STAYS as-is (team-lead didn't ask to migrate them).
- **NEW** privacy + pinnedRoutes = **BACKEND (/settings)** — team-lead's requirement (B) explicitly: NOT localStorage (multi-device Tailscale sync). So the 2 new features go through `useSettings` (`config` + `save(patch)` — fail-closed PATCH → server response), NOT the localStorage sidebar-prefs. (Note: there's a pre-existing `PINNED_ROUTES = ["/"]` in sidebar-prefs = un-hideable routes — a DIFFERENT concept from user-favorite pins; don't conflate.)
- `useSettings` exposes `config: AppConfig | null` + `save(patch)`. FE `AppConfig` type (lib/types.ts) has `wikiAgentAutonomous?` → the 2 new fields add there.
- Sidebar.tsx renders `navGroups` via `useNavGroups()`; privacy + pin hook in at the render layer.

### Decided shapes + persist split (team-lead FINAL, 2026-06-20 — SETTLED after a flip-flop)
> **History (resolved):** team-lead leaned localStorage → reversed to both-backend → RETRACTED back to the original. I'd relayed the reverse mid-flip; sent both teammates a definitive re-correction to land on the FINAL split below. **FINAL = privacy localStorage, pin backend.** No more persistence changes.
- **(A) Privacy = `privacyMode: bool`, persisted LOCALSTORAGE (device-local, NOT backend).** A `lifeos.privacy` flag + `usePrivacy()` hook (read/toggle/broadcast, like useSidebarPrefs). Device-local "someone's watching THIS device" (a public phone shouldn't blur the home desktop). Default false. ON → (1) blur money displays, (2) hide the finance nav group. One bool. **FE-only — NO backend field.**
- **(B) Pin = `pinnedRoutes: list[str] = []`, persisted BACKEND (/settings).** AppConfig field + AppConfigPatch `list[str] | None` mirror (extra=forbid). Ordered routes → a "📌 Ghim" group at the TOP; pin/unpin = PATCH /settings (multi-device sync — Tailscale). Read via useSettings.
- **So the backend change is ONE field (pinnedRoutes); privacy is FE-only (localStorage).** Existing localStorage sidebar hide/reorder prefs untouched. Privacy is cosmetic — typed routes still work, NOT a security boundary.

### Privacy SCOPE (team-lead default + my refinement — logged)
- **Hide the "TÀI CHÍNH" section EXCEPT Macro:** privacyMode ON hides `/decision`, `/finance`, `/portfolio`, `/exchange`, `/journal`, `/market` — but KEEPS `/macro` visible (it's PUBLIC econ indicators — Fed/CPI/DXY — no personal money; team-lead flagged this exact exception). Log: "privacy hides the TÀI CHÍNH money screens; Macro stays (public data). Change the set in the nav-group privacy mapping."
- **Blur targets (the money displays, display-only):** Home tile TỔNG TÀI SẢN + the P&L row (home-pnl-total) + /finance KPIs ($ ) + /portfolio + /exchange totals. **SKIP the Claude $ cost badge** (not money-sensitive, team-lead). Mask = display-only via the data-attr mechanism; real value underneath (recoverable on toggle-off, no reload).

### Privacy blur SCOPE (decided — focused, not an 11-file rewrite)
- Amounts render in ~11 files (page/finance/portfolio/exchange/decision/brief/claude-usage + tiles). Blurring each individually = sprawling.
- **DECISION: a CSS-class mechanism** — a `usePrivacy()` hook/context reads `config.privacyMode`; a shared `<Amount>` wrapper (or a `.privacy-blur` class toggled on the `<body>`/a root data-attr) blurs amount displays. Scope the BLUR to the highest-value money surfaces: the **Home tile money rows + /finance KPIs + /portfolio + /exchange totals** (where the $ is prominent). A `data-amount` attribute + a root `[data-privacy="on"] [data-amount] { filter: blur(6px) }` rule is the cleanest single-mechanism (no per-file logic). FE decides the exact wiring (wrapper vs class) but it must be ONE mechanism, not 11 edits.
- **Hide the finance GROUP:** when privacyMode, the Sidebar drops the "Tài chính" `sec` from navGroups (+ its pinned members if any). The route still works if navigated directly (privacy is a display veil, not access control — single-user, no auth).

## Scope
- IN: (BE) AppConfig/AppConfigPatch += privacyMode + pinnedRoutes (+ md_store persists via the existing path); (FE) the privacy toggle UI (a sidebar/topbar button) + the blur mechanism + hide-finance-group; the pin/unpin UI (a star/pin affordance per route) + the "Ghim" group render; both read/write /settings via useSettings. Tests.
- OUT: NO localStorage for the 2 new features (backend-persisted) · NO migration of the existing hide/reorder localStorage prefs · NO auth/access-control (privacy is a display veil) · NO change to the settings service merge logic (the pattern handles it).

## Dispatch ordering
- **GATING — backend task FIRST:** add privacyMode + pinnedRoutes to AppConfig/AppConfigPatch + the FE types mirror; FREEZE the schema + confirm GET/PATCH /settings round-trips (incl pinnedRoutes: [] clears). Announce frozen.
- **FE task (after the schema freezes):** the privacy toggle + blur + hide-group; the pin UI + "Ghim" group; wire via useSettings. Chrome-verify.

## HARD ACCEPTANCE
- **Backend-persisted (the requirement):** privacyMode + pinnedRoutes survive a PATCH → re-GET → **page reload** (NOT localStorage — verify the value comes from /settings; clearing localStorage doesn't lose it). The multi-device point: it's in md_store, synced.
- **privacy round-trip:** toggle ON → amounts blur + finance group hidden → reload → still ON (from /settings). Toggle OFF → everything back.
- **pin round-trip:** pin /finance → "Ghim" group shows /finance at top → reload → still pinned (from /settings); unpin → gone. pinnedRoutes: [] clears.
- **blur is ONE mechanism** (a class/wrapper/data-attr), not 11 per-file edits; covers the key money surfaces.
- **write-form round-trip (the established discipline):** the toggles are fail-closed writes — submit→2xx→re-GET reflects→persists post-reload; error visible on a failed PATCH.
- pytest (settings) + vitest green, 0 errors; tsc/mypy clean. Chrome-verify both features.

## Risks / seams
- **The localStorage-vs-backend split is the #1 trap:** the existing sidebar prefs are localStorage; the NEW features MUST be backend (/settings). Don't let FE reflexively extend the localStorage sidebar-prefs for pins — that breaks the multi-device requirement. The dispatch names useSettings explicitly.
- **Privacy is a VEIL, not access control** — single-user, no auth; hiding the finance group / blurring amounts is cosmetic (the routes still work if typed). Don't over-build it into a security feature (north-star).
- **pinnedRoutes ordering + dedup:** a route pinned shouldn't also appear duplicated in its normal group (or decide: pinned shows in BOTH the Ghim group AND its home group — simpler, less surprising). Decide: pinned route appears in "Ghim" (top) AND stays in its section (don't remove from home — a pin is an ADD, not a move). FE confirms.
- **Empty states:** no pins → no "Ghim" group (don't render an empty header). privacyMode default false → zero behavior change for existing users.
