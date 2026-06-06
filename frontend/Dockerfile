# frontend/Dockerfile — life-os Next.js frontend (dev-mode).
#
# Single-user local app (CLAUDE.md §2). Runs `next dev` with hot-reload for local
# development. Build with a non-:3010 host port mapping while the live :3010 dev
# server is in use:
#   docker build -t life-os-frontend ./frontend
#   docker run --rm -p 3011:3010 life-os-frontend   # host 3011 → container 3010
#
# Port 3010 per the team's dev-server-ports convention (NOT :3000 = a different
# app on this host). The browser hits the backend at NEXT_PUBLIC_API_BASE — a
# CLIENT-side var baked at build/runtime; since the browser runs on the HOST, it
# must point at the host-published backend port (default http://localhost:8001),
# NOT an in-network service name. Override at build/run if the host port differs.

# node:20-slim per architect's S3B-T2 dispatch (Next 14 supports node 18+).
FROM node:20-slim

# DEVIATION from the dispatch template (npm install + package-lock.json): this
# repo is pnpm-only — there is NO package-lock.json, only pnpm-lock.yaml. Using
# `npm install` would ignore the lock and re-resolve from package.json ranges
# (non-reproducible, can pull newer/different versions). So we use pnpm with the
# committed lockfile. corepack ships with node 20 — enable it + PIN pnpm to the
# lockfile's version (10.18.0): corepack's default (pnpm 11.x) enforces a
# `minimumReleaseAge` supply-chain policy that rejects very-recently-published
# lockfile entries → `--frozen-lockfile` fails on a perfectly valid lockfile.
RUN corepack enable && corepack prepare pnpm@10.18.0 --activate

WORKDIR /app

# Install deps first (layer-cached): copy only the manifest + lockfile so a
# source-only change doesn't bust the dependency layer. --frozen-lockfile makes
# the install reproducible (fails if pnpm-lock.yaml is out of date).
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# App source. .dockerignore keeps node_modules, .next, and caches out.
COPY . .

# Client-side API base — the browser (on the host) reaches the backend via the
# host-published port. Overridable: docker build --build-arg API_BASE=... .
ARG API_BASE=http://localhost:8001
ENV NEXT_PUBLIC_API_BASE=${API_BASE}

EXPOSE 3010

# Dev-mode: `next dev` hot-reloads on edits. -H 0.0.0.0 so the port maps out of
# the container; -p 3010 per the dev-server-ports convention.
CMD ["pnpm", "dev", "-H", "0.0.0.0", "-p", "3010"]
