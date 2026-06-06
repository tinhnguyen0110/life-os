# Plan Sprint 3B — Basic Docker (BE + FE) with runtime mount [Reactive]

> Reactive sprint (CLAUDE.md §3.4b) — same theme as Sprint 3 (infra/runtime that emerged). Triggered by: BE/FE servers don't survive across turns → manual restart every session (:8001 flapping cost rounds all of Sprint 3). User asked for basic Docker so the server stays up + data persists.
> North-star (memory single-dev-no-overengineering): simplest compose that fixes the REAL pain. NO k8s / no prod orchestration / no registry. Real need (not Docker-for-its-sake) = persistent dev servers + no hand-restart.
> Author: architect · 2026-06-06 · Status: awaiting team-lead greenlight.

## The real need (justifies Docker per CLAUDE.md §2)
Sprint 3: :8001 flapped (nohup/setsid/harness-bg none survived turns reliably) → team-lead manually restarted every verify cycle → wasted rounds. `docker compose up` keeps BE+FE running persistently + mounts runtime data → root-cause fix. User: "đăng nào chat phải làm việc này" = the manual restart each chat IS the problem.

## Tasks (2-3, small — pure infra files)
- **T1 [backend] — `backend/Dockerfile`** (dev-mode, simplest):
  - `python:3.11-slim`, install deps from pyproject (`pip install -e .` or `pip install fastapi uvicorn[standard] pydantic pydantic-settings apscheduler httpx pyyaml`), `CMD uvicorn main:app --host 0.0.0.0 --port 8001 --reload`.
  - `--host 0.0.0.0` (NOT 127.0.0.1 — must be reachable from host). `--reload` for dev hot-reload.
- **T2 [frontend] — `frontend/Dockerfile`** (dev-mode):
  - `node:20-slim` (or alpine), `npm install`, `CMD npm run dev` (next dev :3010, hot-reload). Expose 3010.
- **T3 [architect/backend] — `docker-compose.yml`** (repo root) + `.dockerignore` + README note:
  - 2 services `be` (port `8001:8001`) + `fe` (port `3010:3010`), `fe depends_on: [be]`.
  - **Runtime MOUNT (the key ask):** `backend/data/` + `backend/store/` as volumes (md+git store + SQLite persist across restarts, editable on host). Mount `backend/` + `frontend/` source for hot-reload (code change → no rebuild). `node_modules`/`.next` as anonymous volumes (don't mount host's over container's).
  - **CRITICAL — FE→BE URL:** `NEXT_PUBLIC_API_BASE` is CLIENT-SIDE (runs in the user's BROWSER, not the fe container) → it must stay `http://localhost:8001` (the host-published BE port), NOT `http://be:8001` (the compose service name, which only resolves container-to-container). So: BE publishes `8001:8001` to host, FE env keeps `localhost:8001`. (This is the #1 Docker-compose-Next gotcha — get it right.)
  - `.dockerignore`: node_modules, .next, .git, __pycache__, *.pyc, backend/data/.git (the nested runtime repo).
  - README/one-liner: `docker compose up` = the single start command.

## Logic/decisions (decide-and-log)
- **dev-mode (mount source + hot-reload) over build-image** — 1-dev local dev setup, simplest, code edits live without rebuild. (build-image is for prod/ship — not needed.)
- FE = `next dev` (hot-reload) not `next build && start` — dev ergonomics for a personal app.
- BE port 8001 (NOT :8000=OutboundOS), FE 3010 — memory dev-server-ports.
- Mounts persist `backend/data/` (git-versioned md store) + `backend/store/` (SQLite) — survive `docker compose down/up`.

## Defensive / gotchas (MANDATORY)
- `NEXT_PUBLIC_API_BASE=http://localhost:8001` (host port), NOT the service name — client-side fetch from browser.
- BE `--host 0.0.0.0` so the published port actually serves.
- `backend/data/` is its OWN git repo (nested) — mount it but `.dockerignore` its `.git` from the build context; don't let the container reinit it.
- Don't mount host `node_modules`/`.next` over the container's (platform mismatch) — anonymous volumes.
- Port conflict: if :8001/:3010 already taken on host (a bare-metal instance running) → document "stop the bare-metal one first" (don't auto-kill).

## Verification
- `docker compose up` → BE reachable `http://localhost:8001/health` (modules=[market,projects]), FE `http://localhost:3010` loads + ticker shows real prices (FE→BE fetch works through host port + CORS).
- `docker compose down && up` → data persists (a registered project / alert rule survives).
- Survives across turns (the whole point — no manual restart).
- tester: confirm `/health` + `/market` reachable from host + FE renders against the containerized BE. (Light — it's infra, not logic.)

## Sequencing
- Sprint 3 (market) closes FIRST (tester realign + Chrome → commit). 3B is pure infra files → can go in the SAME push or right after. Lean: commit Sprint 3, then 3B as its own small commit (clean separation: market feature vs infra). Architect's call at the time.

## Out of scope (north-star — don't add)
- No k8s, no Docker Swarm, no multi-stage prod build, no image registry, no healthcheck orchestration beyond depends_on, no nginx/reverse-proxy (1 dev, localhost). Add only if a real need appears.
