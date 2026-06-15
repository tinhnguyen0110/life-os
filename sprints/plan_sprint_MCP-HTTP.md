# Sprint MCP-HTTP — streamable-http transport for the 4 MCP servers

**Theme:** Make life-os MCP reachable over **streamable-http** (remote / multi-client), not only stdio.
**Type:** Reactive sprint (single theme, ~1-2 tasks, follows the MCP build-out). Task #48.
**Locked decision (team-lead + architect):** Mount the 4 FastMCP ASGI apps into the EXISTING uvicorn (`:8686`), do NOT spawn 4 new processes/ports. Keep stdio. No auth (single-user localhost — north-star).

## Objective
Each of the 4 servers already has `build_server() -> FastMCP`. FastMCP exposes `.streamable_http_app()` (a Starlette ASGI app) + a lazily-created `.session_manager`. Mount the 4 apps at distinct paths on the FastAPI app in `main.py`, wire all 4 session-manager lifespans into the app lifespan, and update the docs. stdio `main()` entrypoints stay unchanged.

## Mount paths (locked)
| Path mounted in main.py | Server | Tool endpoint (client URL) |
|---|---|---|
| `/mcp/read`       | `mcp_servers.read_server`            | `/mcp/read/mcp` |
| `/mcp/write`      | `mcp_servers.write_server`           | `/mcp/write/mcp` |
| `/mcp/wiki-read`  | `modules.wiki.mcp.read_server`       | `/mcp/wiki-read/mcp` |
| `/mcp/wiki-write` | `modules.wiki.mcp.write_server`      | `/mcp/wiki-write/mcp` |

> NB: a mounted sub-app's INTERNAL streamable_http_path is `/mcp`, so the real client URL is `<mount>/mcp` (e.g. `/mcp/read/mcp`). This is SDK behaviour, not a bug. Documented for the client config.

## Kickoff — 2026-06-15

### SDK facts verified empirically against installed `mcp 1.27.2` (Rule #0 — proven, not assumed)
1. `FastMCP.streamable_http_app()` returns a **Starlette** app; its tool endpoint is at the FastMCP `streamable_http_path` default `/mcp` → so mounted at `/mcp/read`, the client hits `/mcp/read/mcp`.
2. `FastMCP.session_manager` is created **lazily** — accessing it BEFORE `streamable_http_app()` raises `RuntimeError`. So: call `build_server()` → `streamable_http_app()` → THEN read `.session_manager`. Build each app ONCE at app-construction time, hold the FastMCP + app references.
3. `session_manager.run()` is an **async context manager** that MUST run inside the parent app lifespan, or every MCP call 500s. It can be entered **only once per instance** (`_has_started` guard → `RuntimeError` on re-entry). So NEVER build per-request; build once.
4. When you `app.mount(path, sub_app)` a Starlette sub-app into FastAPI, **Starlette does NOT run the sub-app's lifespan** — only the top-level app's lifespan runs. So the 4 `session_manager.run()` MUST be entered explicitly in `main.py`'s lifespan (via `contextlib.AsyncExitStack`). This is the #1 gotcha team-lead flagged — CONFIRMED real.
5. **DNS-rebinding protection (the second, non-obvious gotcha I found):** FastMCP defaults `transport_security.enable_dns_rebinding_protection=True` with `allowed_hosts=['127.0.0.1:*','localhost:*','[::1]:*']`. A request whose `Host` header is NOT in that allowlist gets **`421 Misdirected Request`** — so a REMOTE/multi-client (the whole point of this sprint) is rejected out of the box. Fix: pass `transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)` (single-user, no-auth, LAN — north-star) into each `FastMCP(...)`. VERIFIED: with it OFF, a real `initialize` handshake returns `200` + a session id + capabilities; with it ON (default), `421`.

### End-to-end proof run (architect, before dispatch)
Built all 4 real servers → `streamable_http_app()` each → combined all 4 `session_manager.run()` in one FastAPI lifespan via `AsyncExitStack` → `TestClient` POST `initialize` to each `/<mount>/mcp`. Result: all 4 session managers start + shut down cleanly; with DNS-rebinding OFF the read server returns `200` + valid `mcp-session-id` + full capabilities result. The pattern WORKS on this SDK. `/health` still 200 alongside the mounts.

### Capability gate is UNAFFECTED (confirmed — the locked claim)
`test_mcp_read.py` / `test_mcp_write.py` assert on `vars(rs)`/`vars(ws)` namespace + AST of the module's `import` statements + `build_server()` + `len(TOOLS)`. Mounting happens in `main.py` at the ASGI layer and adds NO import to the server modules. The 4 FastMCP instances stay 4 separate capability sets (read imports zero write symbols — unchanged). So the gate tests are untouched. Only constraint: do NOT add imports to the 4 server modules; the `transport_security` wiring is best done in `main.py` (or a tiny shared helper) so the server modules' import graph stays pristine — see dispatch.

### Drift / risk
- `main.py` currently has a lifespan (`db.init_db()` + scheduler) — GOOD, we extend it, not create one. The 4 `session_manager.run()` nest INSIDE, around the existing `yield`.
- `main.py` lives at `/app` root → it is NOT in any `--reload-dir` allowlist (`core`/`modules`/`store` only). So editing `main.py` does NOT hot-reload — the container must be **restarted** (`docker compose restart backend`) to pick up the mount. Name this in the verification steps so the verifier doesn't read a stale (un-mounted) container as a code bug.

### Final task list
- **T1 (backend):** mount the 4 streamable-http apps + combined lifespan in `main.py`; add `transport_security` (DNS-rebinding OFF) per server; keep stdio `main()` untouched; add an integration test (4 endpoints handshake `200` + distinct session ids + `/health` still 200 + stdio `build_server()` still builds). Update `docs/MCP-CONFIG.md` §3 Transport with the real HTTP section + per-server client URLs.

### Locks (team-lead, 2026-06-15 — after kickoff approval)
1. **`build_server()` signature = approach (B), LOCKED.** Add `transport_security: TransportSecuritySettings | None = None` (default None) to each of the 4 `build_server()` and thread it into the `FastMCP(...)` construction. stdio `main()` calls it arg-less → default-None → byte-identical → gate tests + stdio untouched. `main.py` passes the disabled-protection setting only for the HTTP build. Rationale: DRY (reuses the add_tool loop, no duplicated registration in main.py) + gate-pristine (default-None param adds zero top-level import; keep the `TransportSecuritySettings` hint a lazy/in-fn import or string-annotated). Do NOT have main.py re-build FastMCP from `TOOLS` (approach A — rejected, duplicates registration).
2. **Live-verify Host = NON-localhost (distinguishing case).** The integration test (TestClient, Host=`testserver`) already exercises the 421 path. The tester's LIVE-container curl MUST also send a non-localhost Host (e.g. `-H 'Host: lan-test'`) — because the DNS-rebinding default-allowlist includes localhost, so a localhost-Host curl returns 200 *even if the protection were never disabled* (false-green). A non-localhost Host → 421 if forgotten, 200 if fixed: the only curl that distinguishes fixed-from-broken.

### Sequencing (team-lead)
backend reports done (its own pytest tail + a curl) → architect 4-step review + 3 gates + commit (code + plan + end_sprint, one commit) → architect pings team-lead BEFORE the sleep-120 push → team-lead spawns tester for the independent non-localhost-Host live-container curl inside the 2-min window → push. backend + tester do NOT race on `docker compose restart backend`.
