# backend/Dockerfile — life-os FastAPI backend (dev-mode).
#
# Single-user local app (CLAUDE.md §2 — no auth, no multi-tenant). This image runs
# the API with uvicorn --reload for local development. The container listens
# on :8686; docker-compose publishes it on host :8686.
#
# git is installed because the md_store layer commits markdown writes (store/md_store.py).

FROM python:3.11-slim

# git: required by store/md_store.py (every markdown write = one git commit) AND
# by the projects reader (read-only git log over mounted repos).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Trust mounted repos regardless of uid. The :ro repo mount is owned by the HOST
# uid; the container runs a different uid, so git's safe-ownership check would
# REJECT reading them (fatal: detected dubious ownership) → the reader fail-opens
# every project to health=dead. This tells git to trust any directory. Safe here:
# single-user dev container, repos mounted read-only (no write/ownership risk).
RUN git config --global --add safe.directory '*'

WORKDIR /app

# Install deps first (layer-cached) from the project metadata, then the source.
# Copy pyproject alone so a source-only change doesn't bust the dependency layer.
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# App source. .dockerignore keeps runtime data/, caches, and the venv out.
COPY . .

EXPOSE 8686

# Dev-mode: --reload so code edits hot-reload. Bind 0.0.0.0 so the port maps out
# of the container. Port 8686 (NOT :8000 = OutboundOS).
#
# --reload-dir ALLOWLIST so watchfiles only WATCHES the code dirs, never /app/data
# (the md_store runtime tree — 2200+ git-versioned markdown files). WITHOUT this,
# every wiki/note/journal write (1 git commit each) made watchfiles emit
# `NN changes detected` → CPU/IO churn that contributed to host-load spikes.
#
# Why allowlist, NOT --reload-exclude: uvicorn calls watchfiles `watch(*reload_dirs,
# watch_filter=None)` — it watches the ENTIRE reload-dir tree and applies --reload-exclude
# only AFTER, to decide restart. So --reload-exclude stops the RESTART but watchfiles still
# SCANS data/ and still logs `changes detected` every write. The allowlist removes data/
# from the watch roots entirely → data writes are neither scanned nor logged nor reloaded.
#
# Coverage: core/ + modules/ + store/ are the code the team edits during sprints; they
# hot-reload live. (core/ + modules/ are pure code; store/ also holds db.py + md_store.py.)
#
# store/ holds CODE *and* the live SQLite files (life_os.db / -wal / -shm), which are
# rewritten on every note/market/usage write. Watching store/ naively would re-create the
# storm via .db-wal churn — so we watch store/ but `--reload-exclude` the db files. Per the
# note above, --reload-exclude can't stop watchfiles from SCANNING (a db write still emits
# one `changes detected` line) but it DOES stop the RESTART (the harmful CPU-spinning part).
# store/ db churn is low-volume (a handful of files, occasional writes) vs data/ (2200+ files,
# a commit per write) — so the residual scan-log is negligible; a code edit to db.py/md_store.py
# DOES hot-reload. Verified live: a wiki note write (which hits the SQLite cache) does NOT restart.
#
# DELIBERATELY NOT watched:
#   - /app/data  → md_store git tree (the original storm: 2200+ files, 1 commit/write). Excluded
#                  entirely from the watch roots (not even scanned).
#   - /app/main.py → single file at /app root; watching /app would re-include data/ (the bug),
#                  and uvicorn --reload-dir takes a dir, not a file. main.py is the stable
#                  entrypoint (rarely edited mid-feature); a main.py edit needs `up -d --build`.
# Result (teeth-verified): a code edit under core/ · modules/ · store/ hot-reloads; a data OR
# db write triggers NO restart (data not scanned at all; db-file scan logged but never reloads).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8686", "--reload", \
     "--reload-dir", "/app/core", "--reload-dir", "/app/modules", "--reload-dir", "/app/store", \
     "--reload-exclude", "*.db", "--reload-exclude", "*.db-wal", \
     "--reload-exclude", "*.db-shm", "--reload-exclude", "*.db-journal"]
