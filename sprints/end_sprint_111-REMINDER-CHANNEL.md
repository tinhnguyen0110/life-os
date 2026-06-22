# end_sprint_111-REMINDER-CHANNEL — reminder delivery channel (BE half) (Cairn #111, TRACING-UX T3)

> Result. Reminders fired only via the severity-routed alerts engine — no user-pickable channel. Added a `channel` (in_app|email|discord) to reminders, routed via the #33 alerts engine (the kickoff-reconciled design — NOT the task's outdated "#29 dispatcher"). Commit `<hash>` `feat(sprint-111-reminder-channel): channel select via alerts engine, available-flags, no-double-fire (#111 BE)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live teeth — all 3 nuances). Cairn #111 TRACING-UX T3 — BE half; **#111 stays OPEN (BE-verified / FE-pending** — the channel <select> picker is the FE lane). user-CHỐT.

## What shipped (reminders + alerts + tracing + MCP + tests)
| File | Change |
|---|---|
| `alerts/service.py` (`notify`) | `+channels: list[str] \| None = None` — OMITTED → BYTE-IDENTICAL severity route (pre-#111); GIVEN → route to EXACTLY those channels, severity-independent (the additive override, option a). + `discord_configured()`/`mail_configured()` public detection helpers. |
| `reminders/schema.py` | `ReminderInput +channel: Literal["in_app","email","discord"] = "in_app"` (user-settable, default in_app — distinct from forge-guarded `source`); `Reminder +channel`. |
| `reminders/store.py` | channel column + idempotent migration (column-exists guard; default 'in_app' for existing rows). |
| `reminders/service.py` | `notify_scan` routes the fire by channel: 🔴 in_app → NO alerts call (the row exists in /reminders UI; calling alerts = double-fire); email/discord → `alerts.notify(..., channels=[channel])`. `_channel_available` REUSES alerts' detection; `list_channels` → [{id,label,available,reason?}]; unavailable-set → fallback in_app + warning. |
| `reminders/router.py` | `GET /reminders/channels`. |
| `tracing/{schema,store,service}.py` | `ActivityInput +remindChannel` (camel, like remindAt) → the linked reminder gets that channel (source=tracing one-way #75). |
| `mcp_servers/{read_server,reminders_server}.py` | `reminders_channels` tool (parity #24); reminder list carries `channel`. |
| tests (+22, 2274→2296) | the 3 nuances + default/bad-channel/migration/parity/tracing-e2e. |

## Design (LOCKED — alerts-engine reconcile, 3 nuances, in_app-no-double-fire)
- **🔴 KICKOFF DRIFT RECONCILED:** the task said "route via the #29 dispatcher" — but #33 (ALERT-ROUTING) removed the per-module poster + built the shared `modules/alerts` engine. So #111 routes via alerts.notify (NOT a new dispatcher) — the §3.3a kickoff caught this before backend built the wrong thing.
- **nuance 1 — channels= additive, severity-no-regression:** `alerts.notify(channels=)` OMITTED = the exact pre-#111 severity route (the #33 scan + future callers unaffected); GIVEN = exactly those channels, severity-independent. Both paths tested.
- **nuance 2 — available-flags REUSE alerts:** `_channel_available`/`list_channels` call `alerts.discord_configured()`/`mail_configured()` — the SAME helpers /alerts/config uses (one source, can't drift). `GET /reminders/channels` == /alerts/config detection.
- **🔴 nuance 3 — in_app = NO alerts call (no double-fire):** the fire branch is `if channel in ("email","discord"): alerts.notify(...)` — in_app (the default) skips alerts entirely (the reminder row already shows in /reminders UI; an alerts call would be a double-fire). The engine's counter/roll/cap still advance (unchanged) — only WHERE a fire goes changed.
- **unavailable-set → fallback in_app + warning** (honest-mirror, not silent). bad channel → 422.

## Verification (Rule#0 — architect INDEPENDENT, restarted container)
- **architect 4-step (read FULL):** channels= additive (severity unchanged when omitted); _channel_available reuses alerts; the notify_scan branch gates the alerts call on email/discord (in_app skips → no double-fire); read_server.py staged is #111-only (reminders_channels, NO #112 projects — the shared-file serialization, commit before #112). ✅
- **🔴 INDEPENDENT live teeth (restart-then-call):**
  - severity-route intact (channels omitted, normal → discord fires); channel-override (channels=[discord], low-sev → discord fires regardless of severity). ✅
  - /reminders/channels reuses alerts detection (in_app always true; discord avail == alerts.discord_configured()). ✅
  - 🔴 notify_scan with in_app → 0 alerts calls (no double-fire; the branch gates on email/discord). ✅
  - bad channel "telegram" → ValidationError (422); default = in_app. ✅
- **Suite:** #111 files (channel/alerts/notify/mcp count-asserts) 207 passed; backend reverse 2296/0; architect forward <COUNT> (the one OKX flake = #116 pre-existing reverse-order leak, NOT #111 — finance untouched by #111). never staged backend/data/.

## 3 Gates
- **Gate 1 (API/MCP/agent):** channel field (user-settable, default in_app); GET /reminders/channels (available-flags, agent-readable); bad→422; unavailable→fallback+warning; MCP reminders_channels parity. ✅
- **Gate 2 (Function):** the 3 nuances (severity-no-regression / available-reuse / in_app-no-double-fire) + default + 422 + migration-idempotent + tracing-e2e; independent live; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged the #111 BE files (NO #112 projects, no data/.env); read_server.py #111-only (serialization); commit format. ✅

## Assumptions (user-review)
- **channel routes via the #33 alerts engine** (channels= additive override), NOT a new dispatcher. **Why:** #33 already centralized delivery; the task's #29-dispatcher framing was pre-#33. **How to change:** the notify_scan channel branch + alerts.notify.
- **in_app = the existing reminder row, NO external send** (default). **How to change:** if in_app should also notify externally, add it to the email/discord branch (NOT recommended — double-fire).
- **email/discord availability = whether .env creds present** (reuses alerts). **How to change:** add creds → the channel auto-enables; add a new channel = +1 enum + 1 dispatcher branch.

## Notes
- Cairn #111 TRACING-UX T3 BE half — user-CHỐT (reminder channel select). backend-w3 built; architect committed (§3 sole-committer). **The §3.3a kickoff's value:** caught the task's pre-#33 "#29 dispatcher" drift → reconciled to the shared alerts engine BEFORE backend built it wrong; team-lead's 3 wiring nuances (severity-no-regression, available-reuse, in_app-no-double-fire) all landed + tested. The in_app-no-double-fire is the load-bearing correctness piece (an in_app fire makes 0 alerts calls). Committed BEFORE #112 (shared read_server.py — #111-only staged, serialization held #109→#111→#112). **#111 stays OPEN (BE-verified/FE-pending)** — the channel <select> picker is the FE lane (→ frontend-w3-2). The forward #116 OKX flake is the pre-existing reverse-order leak (logged), NOT #111 (finance untouched).
