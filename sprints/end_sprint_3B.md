# End Sprint 3B — Basic Docker (BE + FE) dev runtime [Reactive]

> Reactive sprint (CLAUDE.md §3.4b), same theme as Sprint 3 (infra). Triggered by: BE/FE servers didn't survive across turns → manual restart every session (:8001 flapping cost rounds all of Sprint 3). User asked for basic Docker so the server stays up + data persists.
> North-star: simplest compose that fixes the REAL pain. NO k8s/prod-orchestration/registry/nginx.
> Author: architect · 2026-06-06 · Commit: `chore(sprint-3B)`.

---

## 1. What shipped
- **`backend/Dockerfile`** (backend): python:3.11-slim + git (md_store needs it) + `pip install .` from pyproject, `uvicorn main:app --host 0.0.0.0 --port 8001 --reload`, EXPOSE 8001. Built (275MB), ran verified.
- **`frontend/Dockerfile`** (frontend): node:22-slim + pnpm 10.18.0 pinned (corepack 11.x's `minimumReleaseAge` supply-chain policy rejects fresh lockfile entries → pin the version that built the lockfile), `pnpm install --frozen-lockfile`, `pnpm dev -H 0.0.0.0 -p 3010`, `ARG/ENV API_BASE=http://localhost:8001` (overridable), EXPOSE 3010. Built + ran verified.
- **`docker-compose.yml`** (architect): 2 services — `backend` (8001:8001) + `frontend` (3010:3010), `frontend depends_on backend`. Volume mounts: `./backend/data` + `./backend/store` (persist md+SQLite across restarts), source dirs (hot-reload), `node_modules`/`.next` anonymous (don't let host shadow container). `API_BASE` (build arg + env) = `http://localhost:8001` — the host-published BE port, NOT the `backend` service name (client-side, browser).
- **`.dockerignore`** ×2 (backend + frontend, kept from T1/T2 — Option A): exclude `data/.git` (nested md-store repo), `__pycache__`, `*.pyc`, venv, db, `.env`, `node_modules`, `.next`, caches.
- **One command:** `docker compose up` (documented in compose header).

## 2. Verification (Rule #0 — real build + run, not just authored)
| Check | Result |
|---|---|
| `docker compose config` | valid |
| `docker compose build` (both images) | life-os-backend + life-os-frontend Built (exit 0) |
| `docker compose up` (temp ports 8005/3015, bare-metal untouched) | both containers running |
| BE `/health` through container | modules=[market,projects], routines=[market-poll,wiki-refresh] |
| BE `/market` through container | 5 assets, BTC $60,379 source=coingecko (REAL price through container) |
| BE `/projects` through container | reads mounted DATA_DIR |
| FE `/` + `/market` through container | 200 (Next dev serving in container) |
| **API_BASE gotcha** | FE JS bundle calls `localhost:<host-port>` (build-arg), NOT `backend:8001` service name — the #1 compose-Next trap, handled |
| Mount persist | BE reads data/store volumes |
| bare-metal :8001 during test | untouched (200) — temp-port test didn't disrupt the live instance / user |

Tested on temp ports (8005/3015) to avoid killing the bare-metal :8001/:3010 while the user was mid strategy-discussion (infra courtesy). The canonical compose uses 8001/3010; the final switch (stop bare-metal → `docker compose up` on 8001/3010 → Chrome round-trip, CORS passes on :3010) is team-lead's infra-lane handover.

## 3. Assumptions (decide-and-log)
- **Dev-mode (mount source + hot-reload) over build-image** — 1-dev local; code edits live without rebuild. To ship a built image later, add a prod target (not needed now).
- **FE = `next dev`** (not `build && start`) — dev ergonomics.
- **pnpm 10.18.0 pinned** — corepack default (11.x) enforces `minimumReleaseAge` that rejects <12h-old lockfile entries → build fails; pin the lockfile's version. Don't bump pnpm without regenerating pnpm-lock.yaml.
- **API_BASE = http://localhost:8001** (host port, client-side). To change the FE port mapping, update both the compose port + the API_BASE arg/env together.
- **Mounts persist `backend/data` + `backend/store`** across `docker compose down/up`.

## 4. Risks / notes
- **CORS + non-standard ports:** if the user maps FE to a non-3010/3000 port, `cors_origins` must include that origin (currently [:3010, :3000] + LIFEOS_CORS_ORIGINS override). On the canonical 3010 it's fine.
- **`/projects` through container shows only repos visible to the container** — `project_repos` config points at host paths the container doesn't mount (ref-not-embed: real repos live outside). If the user wants the container to read the real repos, mount their parent dir + adjust paths. Out of scope for "basic dev runtime"; flag for a later infra tweak.
- **Image size** (BE 275MB) — fine for local; slim later only if it matters.

## 5. Retro
- The :8001-flapping that cost rounds all of Sprint 3 is now root-caused: ephemeral bare-metal servers don't survive turns. `docker compose up` is the fix. (The deeper process lesson — verify-after-write + behavior-test + full-suite-on-staged — was about catching drift; this removes a whole class of infra friction.)
- API_BASE-is-client-side was the one real Docker trap; flagging it in the plan upfront (architect design vs improvise) meant it was handled, not debugged after.

## 6. Commit
- `chore(sprint-3B): docker compose for BE+FE dev runtime` — compose + 2 Dockerfiles + 2 .dockerignore + plan/end docs. Separate from `feat(sprint-3)` (infra vs feature). Then `sleep 120 && git push` + notify. Final port-switch to 8001/3010 + Chrome round-trip = team-lead infra handover post-commit (or pre-commit if cleared).
