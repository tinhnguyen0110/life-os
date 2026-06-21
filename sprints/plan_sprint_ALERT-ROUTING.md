# Sprint ALERT-ROUTING — general notify routing engine (Cairn #33, the user-asked "alert đâu")

> Created 2026-06-21 by architect. PRIORITY (user explicitly asked "alert đâu"; env app-password ready). DESIGN to team-lead BEFORE dispatch — mail is a NEW external side-effect channel (contract-ish). The GENERAL notify engine ALL life-os alerts route through (reminders-notify #29 + future). backend.

## Objective
life-os has a Discord poster (the #29 reminders `_notify`/`_discord_webhook`) but no GENERAL alert engine + no mail channel. #33 = a single `notify(severity, title, body)` that ROUTES by severity: Discord always; Mail on high. All alerts (reminders-notify now, future alerts) route through this ONE engine — no per-module notify duplication.

## The engine (DECIDED — decide-and-log; team-lead sanity-check the threshold + mail)
A shared module `modules/alerts/` (BaseModule, registry-discovered) exposing:
- **`notify(severity: Literal["low","normal","high"], title: str, body: str) -> dict`** — the single entry point.
- **Routing (DECIDED default):**
  - `low` / `normal` → **Discord only** (the always-on feed; no mail noise).
  - `high` → **Discord + Mail** (mail = the louder, reserve-for-urgent channel).
  - Threshold = "mail fires at `high`". (decide-and-log: a config knob `alertMailThreshold` default `high` so the user can lower it to `normal` later — but ship the constant, don't over-build a settings UI.)
- **Discord:** GENERALIZE the #29 `_discord_webhook()` + `_notify()` (read `.env discord=`, urllib, fail-SOFT) — move/share it here so reminders-notify calls THIS engine instead of its own copy (de-dup). Message format: `[{severity}] {title}\n{body}`.
- **Mail (NEW channel):** SMTP via `LIFEOS_SMTP_USER` + `LIFEOS_SMTP_APP_PASSWORD` (Gmail app-password, both confirmed in `.env`). stdlib `smtplib` + `ssl` (SMTP_SSL to smtp.gmail.com:465), To = LIFEOS_SMTP_USER (self-send, single-user), Subject = `[life-os {severity}] {title}`, body = `body`. **fail-SOFT** (an SMTP error → log + continue, NEVER crash the caller — same contract as the Discord poster; a routine/caller's primary work must not fail because mail bounced).
- **Return** `{discord: bool, mail: bool, severity}` (which channels actually fired) so the caller/test can assert.
- **NO new external dep** — smtplib/ssl are stdlib (no-overengineering).

## ⚠️ FORK (team-lead — mail is a new side-effect channel)
- **F1 — mail threshold default:** I chose `high` → Discord+Mail; low/normal → Discord-only. Alt: `normal`+ → mail (chattier). I lean `high` (mail = urgent-only, avoids inbox spam for a single user). **Confirm or set the threshold.**
- **F2 — which existing events escalate to mail?** reminders-notify (#29) currently Discord-only. After #33, should an OVERDUE reminder be `high` (→ mail)? I lean: reminders-notify maps due→`normal` (Discord), overdue-past-cap→`high` (mail) — so a genuinely-missed reminder reaches the inbox. (decide-and-log; surface for the sanity-check — this rewires #29 to call the shared engine.)
- **F3 — confirm self-send** (To = LIFEOS_SMTP_USER, single-user) is the intended recipient (no separate "alert recipient" address). I assume yes (single-user).

## Tasks (after team-lead's design OK)
- **T1 (backend, gating):** `modules/alerts/` — `notify()` + the Discord (generalized from #29) + the Mail (smtplib, app-password, fail-soft) + the routing + config threshold. Tests (mockable smtp + webhook; assert routing per severity, fail-soft on both channels).
- **T2 (backend):** rewire reminders-notify (#29) to call `alerts.notify(...)` instead of its own `_notify` (de-dup; severity map per F2).
- **T3 (tester):** routing distinguishing (low/normal→Discord-only; high→both); fail-soft both channels (mail bounce + webhook error → caller doesn't crash); mockable so no real mail/Discord sent.
- **T4 (architect):** review + commit `feat(sprint-ALERT-ROUTING)`.

## HARD GATE (distinguishing)
- `notify("low",…)` + `notify("normal",…)` → Discord fired, Mail NOT (return {discord:True, mail:False}).
- `notify("high",…)` → BOTH fired (return {discord:True, mail:True}).
- Mail SMTP error → notify returns {mail:False} but does NOT raise (fail-soft); Discord error likewise.
- reminders-notify routes through alerts.notify (no duplicate webhook code; grep: reminders no longer has its own _discord_webhook OR it delegates).
- mockable smtp/webhook in tests — NO real send. pytest green, mypy clean.

## Baseline
pytest 1832 (post-877b24e). Keep 0-failed.

## Assumptions (user-review)
- **general notify(severity, title, body) routing engine** — low/normal→Discord; high→Discord+Mail (threshold `high`, config knob `alertMailThreshold`); Discord generalized from #29, Mail via SMTP app-password (LIFEOS_SMTP_*), both fail-soft; self-send (To=SMTP_USER). **How to change:** the threshold constant/config + the channel posters in modules/alerts.
- **reminders-notify rewired** to the shared engine: due→normal(Discord), overdue-past-cap→high(Discord+Mail). **How to change:** the severity map in reminders-notify.

## Notes
- PRIORITY (user-asked). BRING DESIGN to team-lead before dispatch (mail = new side-effect channel). Separate commit `feat(sprint-ALERT-ROUTING)`.
- Parallel to #34 wiki auto-suggest (different module) but backend = 1 implementer → #33 FIRST (priority), #34 pipelines.
