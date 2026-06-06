# backend/Dockerfile — life-os FastAPI backend (dev-mode).
#
# Single-user local app (CLAUDE.md §2 — no auth, no multi-tenant). This image runs
# the API with uvicorn --reload for local development. Build with a non-:8001 host
# port mapping while the live :8001 instance is in use:
#   docker build -t life-os-backend ./backend
#   docker run --rm -p 8002:8001 life-os-backend   # host 8002 → container 8001
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

EXPOSE 8001

# Dev-mode: --reload so code edits hot-reload. Bind 0.0.0.0 so the port maps out
# of the container. Port 8001 per the team's dev-server-ports convention
# (NOT :8000 = OutboundOS).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
