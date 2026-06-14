# Plan — Sprint W1-FE · Wiki screens W2 (Note view/edit) + W3 (Inbox/Refine)

> Frontend's FIRST Wiki work. FE-first-after-freeze: mirror the FROZEN M1 backend contract (`1b5a03c`, 12 endpoints) + port the mock. NO backend change.
> Mock (the contract): `template/Life Command/app/screens-wiki.js` (SCREENS.note=W2, SCREENS.inbox=W3) + `data-wiki.js` (DB shapes) + `wiki.css` (tokens). Frozen API: `end_sprint_W1c.md §3`.
> Author: architect · 2026-06-13.

---

## Objective

Ship two real Wiki screens against the frozen M1 backend: **W2 `/wiki/[id]`** (read/edit one note + all its connections) and **W3 `/wiki/inbox`** (triage fleeting notes with the ≥1-link hard gate). Build the shared components the rest of the Wiki UI will reuse (WikiLinkRenderer, minimal markdown viewer/editor, BacklinksPanel, TrustTierBadge), wire the nav "Tri thức" group, and mirror the frozen Note/backlinks/inbox shapes into `types.ts`. Render-only for AI-derived fields (empty at M1 — show the empty state, never fabricate).

## Scope

**IN:**
- **`lib/types.ts`** — mirror the FROZEN shapes VERBATIM: `WikiNote` (id/title/aliases/status/noteType/trustTier/author/tags/content/created/updated/contentHash), `WikiBacklinks` ({linked:[{id,title,snippet,anchor?}], unlinked:[{id,title,snippet}], outbound:[{id,title,isResolved}|{ghost,isResolved:false}]}), `WikiInbox` ({items:[{id,title,status,rawContent,captured,captureSource,linkCount,aiSuggest:null}]}), `WikiSuggestion` (candidates — empty at M1), enums Status/NoteType/TrustTier.
- **`lib/api.ts`** — wiki methods: `getNote(id)` · `createNote(input)` · `updateNote(id,input)` · `deleteNote(id)` · `getBacklinks(id)` · `refineNote(id,input)` · `getInbox()` · (search/overview/graph/merge can stub now or land with W1/W4 — W1-FE needs note+backlinks+inbox+refine). Reuse the `{success,data,warning?}` envelope + `ApiError.fieldErrors()` for the refine 422.
- **`lib/useWiki.ts`** (or `useWikiNote`/`useWikiInbox`) — hooks following the existing `useNotes.ts` pattern (fetch + mutate + refetch-after-write, NO optimistic splice — fail-closed, the W1c-frozen recompute comes from the refetch).
- **W2 `/wiki/[id]` screen** (`app/wiki/[id]/page.tsx`): header (title editable, `#id`, status pill editable-in-place, aliases, tags, created/updated) + **TrustTierBadge** (verified/candidate + the candidate-warning banner if trustTier=candidate + noteType concept/literature) + **markdown body** rendered via **WikiLinkRenderer** + **edit mode** (markdown editor, save → updateNote) + **outbound** (resolved → clickable link, ghost → "+ tạo note") + **BacklinksPanel** (linked mentions clickable + snippet; unlinked mentions + "link nó" button; — unlinked IS populated now from W1c) + **AI link-suggestions panel render-EMPTY** (M1 has no AI — show "no suggestions yet / coming via Claude Code" empty state, accept/reject/pin buttons present but the list is empty; DON'T fabricate).
- **W3 `/wiki/inbox` screen** (`app/wiki/inbox/page.tsx`): fleeting list (rawContent snippet + captured + captureSource + linkCount) → select → **refine panel** (edit title/content/status/tags + the `[[]]` link affordance) → **Done refine** calls `refineNote` → **≥1-link HARD GATE: a 422 surfaces VISIBLY** ("refine requires ≥1 link") + the **cold-start case shows the warning** (not an error) + progress count "N → 0". AI aiSuggest panel render-empty (M1).
- **WikiLinkRenderer** (shared): parse `[[id|title]]`→`<Link>` to /wiki/id, `[[id]]`→`#id` link, `[[Title]]` (no id) → ghost-styled span (per mock regex lines 20-25). Minimal markdown (in-house, no heavy lib per FE recon) — headings/bold/lists/paragraphs + wikilinks. 
- **nav.ts** — add the **"Tri thức"** group: Wiki Home (`/wiki`) · Inbox (`/wiki/inbox`, badge N fleeting) · (Graph/Proposals later). W2 `/wiki/[id]` is a detail route (CRUMB entry, not a top nav item).
- Port `wiki.css` tokens into the app's styling approach (don't redesign — port).
- Tests: vitest for WikiLinkRenderer (all 3 link forms + ghost), BacklinksPanel (linked/unlinked/outbound/ghost render), refine-gate UI (422 visible, cold-start warning), hook fetch/mutate.

**OUT (later — name them):**
- W1 Vault Overview screen (`/wiki`) + W4 Graph + W5 MOC + P1 Proposal Queue → later FE sprints.
- AI suggestion POPULATE (accept/reject/pin wired to a real backend) → M4 (render the empty state now).
- Command-bar wiki verbs (`note`/`link`/`find`) → a shell-touching task later.
- Sidebar badge LIVE wiring (the existing `sidebar-badges-static-placeholder` debt) — W1-FE adds the Tri thức group with a static/inbox-count badge; full live-badge wiring is the separate shell task.

## Per-screen mock + schema mapping (FE dispatch standard — `dispatch-standards-additions`)
| Screen | Mock to port | Frozen API it consumes | Derived (backend computes — render only) |
|---|---|---|---|
| W2 `/wiki/[id]` | `screens-wiki.js` `SCREENS.note` (L151+) + `wiki.css` | `GET /wiki/notes/:id` + `GET /wiki/notes/:id/backlinks` · edit→`PUT /wiki/notes/:id` | backlinks (linked/unlinked/outbound/ghost), isResolved, trustTier — all server-computed; FE renders. AI suggestions = empty. |
| W3 `/wiki/inbox` | `screens-wiki.js` `SCREENS.inbox` | `GET /wiki/inbox` · refine→`POST /wiki/notes/:id/refine` | linkCount server-side; the ≥1-link gate is ENFORCED server-side (422) — FE surfaces it, does NOT reimplement the rule. aiSuggest = null. |

## Tasks (3, frontend-only; T1 gating — shared layer)
- **T1 — types + api + hooks + shared components (GATING).** `types.ts` mirror frozen shapes · `api.ts` wiki methods · `useWiki*` hooks · **WikiLinkRenderer + minimal markdown viewer/editor + BacklinksPanel + TrustTierBadge** (shared, reusable). Vitest for the renderer (3 link forms + ghost) + components. Everything W2/W3 build on.
- **T2 — W2 Note view/edit screen.** `app/wiki/[id]/page.tsx` — header/status-pill/aliases/tags + TrustTierBadge + candidate-warning + body via WikiLinkRenderer + edit mode (save→PUT, refetch) + outbound + BacklinksPanel + AI-suggestions empty-state. nav CRUMB for /wiki/[id]. Chrome self-verify.
- **T3 — W3 Inbox/Refine screen + nav group.** `app/wiki/inbox/page.tsx` — fleeting list + refine panel + refineNote + **≥1-link gate 422 VISIBLE** + cold-start warning + progress count. nav.ts "Tri thức" group + Inbox badge. Chrome self-verify (the refine round-trip + the visible 422).

## Runtime / Baseline / Deps / Exports / Test split / Verification / Ownership / Idle
- **Runtime:** `docker compose up -d` (DETACHED). **FE :3010 · BE :8686** (memory `dev-server-ports`, BE is :8686 NOT :8001). FE reaches API via `NEXT_PUBLIC_API_BASE=http://localhost:8686` (compose-set; the api.ts `:8000` fallback is for bare-metal only — rely on the env). **Verify the canonical stack is UP before Chrome self-verify** (`curl :8686/health` + FE :3010 loads) — first Wiki FE work, don't assume.
- **Baseline:** vitest **383** (FE untouched since foundation), pytest 853 (backend frozen — FE adds NO pytest). Additive → vitest > 383.
- **Dependencies:** frozen M1 backend (`1b5a03c`, 12 endpoints) — all live on :8686. Existing FE: `api.ts`/`types.ts`/`nav.ts`/`use*.ts`/`components/shared` patterns + `useNotes.ts` as the closest model. No backend change.
- **Exports (for tester):** the routes `/wiki/[id]` + `/wiki/inbox` + the components (WikiLinkRenderer, BacklinksPanel, TrustTierBadge) + hooks. Tester Chrome-verifies the live screens + the refine round-trip.
- **Test split:** frontend writes vitest (renderer, components, hooks, refine-gate UI) + does its OWN Chrome self-verify (Gate 2 FE tick). Tester does the independent Chrome UI verification (Gate 3) + the write-form round-trip teeth.
- **Verification (ONE bar):** W2 renders a real note (GET) + edit saves (PUT→refetch reflects, persists post-reload) + WikiLinkRenderer 3 forms + ghost styled + BacklinksPanel linked/unlinked/outbound/ghost render + candidate badge/warning · W3 refine: ≥1-link → saves+status flip; **0-link non-cold-start → VISIBLE 422 error in UI** (not swallowed); cold-start → warning shown · AI panels show empty-state (NOT fabricated) · vitest ≥383 + 0 errors/unhandled (`unhandled-errors-not-green`) · tsc clean · Chrome self-verify done. **write-form round-trip** (`write-form-roundtrip-verify`): submit→2xx→re-GET reflects→persists post-reload (3 values agree); force the swallowed-422 + partial-write + optimistic-over-failed-POST cases.
- **Ownership:** vitest fail → frontend fixes. Tester reports Chrome/round-trip findings w/ repro, never edits. Contract mismatch (FE expects a field backend doesn't return) → escalate to architect (don't fabricate — memory `dispatch-verify-fields-exist-on-schema`); the frozen contract is `end_sprint_W1c §3`.
- **Idle:** task done → SendMessage team-lead w/ evidence (vitest count + tsc clean + a Chrome screenshot/console-clean of the live screen + the refine 422 shown) + TaskUpdate. Blocked/contract-gap → SendMessage team-lead FIRST.

---

## Kickoff — 2026-06-13
### Drift check
- Frozen M1 backend stable at `1b5a03c` (12 endpoints, 853/0). FE untouched since the foundation (vitest 383).
- FE patterns confirmed: `api.ts` (typed client + `ApiError.fieldErrors()` — IDEAL for the refine 422 per-field surface) · `nav.ts` NavGroup[] + badge · per-feature `use*.ts` hooks (`useNotes.ts` is the closest model — fetch + mutate + refetch) · `components/shared/`. WikiLinkRenderer + md viewer/editor + BacklinksPanel are genuinely NEW (frontend recon confirmed; minimal in-house markdown, no heavy lib).
- Mock-diff (`screens-wiki.js` SCREENS.note/inbox + `data-wiki.js` vs scope): W2 + W3 covered. The mock's AI panels (suggestions accept/reject/pin, aiSuggest) → **render the empty state at M1** (no embedded AI — M4 populates). This is the inverse-of-dropped: a real panel that's intentionally empty (tester: NOT a dropped feature). NoteRESPONSE has no `archived`/`degree` for W2 (degree is a graph/overview field) — W2 doesn't need them.
- ⚠️ `api.ts` BASE fallback is `:8000` (OutboundOS!) when env unset — the dispatch must stress: rely on `NEXT_PUBLIC_API_BASE=:8686` (compose-set); never hit the :8000 fallback. (Existing screens already work via the env, so this is fine in-container — just flag it.)
### Decisions (decide-and-log → end_sprint_W1-FE §Assumptions)
- AI suggestion/aiSuggest panels render an EMPTY STATE at M1 (not fabricated, not hidden — the panel exists, says "coming via Claude Code / no suggestions yet"). Honest-mirror: the feature shape is present, populated at M4.
- Minimal in-house markdown renderer (no heavy lib) — headings/bold/italic/lists/paragraphs + wikilinks. Per FE recon + no-overengineering.
- refetch-after-write (fail-closed), NO optimistic splice — the recompute (backlinks/linkCount) comes from the server refetch.
- ≥1-link gate is ENFORCED server-side (422); FE SURFACES it visibly, does NOT reimplement the rule client-side (single source of truth).
- W1 Vault Overview screen NOT in this sprint (W2+W3 only per team-lead scope) — the nav "Tri thức" group links to /wiki (will 404/stub until the W1 screen sprint) OR point the group's first item at /wiki/inbox for now. **DECISION: nav group lists Inbox (live) + Wiki Home (/wiki — note if it's not built yet, either stub it minimally or defer the /wiki nav item to the W1 screen sprint).** Flag to team-lead: do we want a minimal /wiki stub this sprint to avoid a dead nav link, or defer the Home nav item? → recommend: add ONLY the Inbox nav item (live) this sprint; add Wiki Home + Graph + Proposals when those screens land (no dead links — `milestone-audit-grep-all-stubs`).
### Final task list
- T1 types + api + hooks + shared components (WikiLinkRenderer/md/BacklinksPanel/TrustTierBadge) — GATING
- T2 W2 Note view/edit screen
- T3 W3 Inbox/Refine screen + nav "Tri thức" group (Inbox item only, no dead links)
