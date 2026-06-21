# end_sprint_DAILY-TRACING-P2 — MCP tracing_overview + tracing_log (Cairn #65 Phase 2)

> Result. The MCP agent surface for the tracing module: a tracking agent reads its habit board (tracing_overview) + logs a session (tracing_log) over MCP. Commit `<hash>` `fix(sprint-DAILY-TRACING-P2)`. Status: ✅ all gates pass. backend-w3 BUILT (read-server wire + new tracing_server + tests); architect 4-step + LIVE-HTTP verified + committed (§3, sole serialized committer). Phase 2 of 4 (P1 BE → **P2 MCP** → P3 FE → P4 brief).

## What shipped (4 code + 4 test files)
| File | Change |
|---|---|
| `mcp_servers/read_server.py` | + `tracing_overview()` on the SHARED read surface — `_tracing_overview().model_dump()` (byte-identical to GET /tracing, #24). Read-fn import + TOOLS entry + `_CATALOG_MOUNTS` ("tracing", ...). Shared-read count 42→43. |
| `mcp_servers/tracing_server.py` (NEW) | the per-domain `lifeos-tracing` server (clone of reminders_server). `tracing_overview` = reference-import from read_server (is-identity anti-dup spine). `tracing_log(activity_id, val, dur_min?, note?)` = DIRECT write-through (`service.log_session`) → `{logged, activityId, activity:ActivityView}`; unknown→`{found:False, activityId}`; val<0 → LogInput validator raises. build_server/main mirror. |
| `main.py` | + 1 `_MCP_MOUNTS` line `("/mcp/tracing", "mcp_servers.tracing_server")` — inherits stateless_http + DNS-off per the per-domain pattern. |
| `mcp_servers/CATALOG.md` | + tracing domain section (2 tools, writable, generator-covered). |
| `tests/test_mcp_read.py` · `test_mcp_http.py` · `test_finance_mcp_shape.py` | the count-43 consumers updated (multi-line-grep clean, no stray 42/41). |
| `tests/test_mcp_http.py` (extra) | **fixed the stale MOUNTS gap** (+`/mcp/reminders` +`/mcp/tracing`; "5 mounts"→"7 mounts") AND added `test_MOUNTS_in_sync_with_main_mcp_mounts()` — pins MOUNTS == main._MCP_MOUNTS so a future mount can't silently lose handshake/stateless coverage (the structural fix). |
| `tests/test_tracing_mcp_server.py` (NEW, 168, 11 tests) | the dedicated distinguishing set (is-identity, byte-identical-to-REST via json.dumps sort_keys, write-through, accumulate round-trip, unknown→found:false, negative→raises+no-row, no-mutate-gate guards, CAN-mutate boundary). |

## Design (LOCKED — per-domain MCP, REST≡MCP)
- `tracing_overview` reference-imported (is-identity) — one read fn on lifeos-read AND lifeos-tracing, no drift (the per-domain anti-dup spine).
- `tracing_log` = DIRECT write-through (single-user, append-only, REVERSIBLE data, no trust boundary → no proposal gate; KEPT OFF the whole-app write-server to preserve its no-mutate AST gate).
- REST≡MCP byte-identical (#24): tracing_overview structuredContent == GET /tracing data.
- existence-contract (MCP convention): unknown id → `{found:False}`, NOT an error/crash (mirrors reminder_tick).

## Verification (Rule#0 — architect 4-step + LIVE HTTP + backend evidence)
- **architect 4-step (read full fns on disk):** tracing_server = clean reminders clone (overview ref-import is-identity; log direct write-through w/ existence-contract + validator-raise) ✅; read_server tracing_overview = the byte-identical wrapper ✅; main.py 1 mount line (registry contract — NO core edit) ✅; the count-43 consumers consistent across 3 files (multi-line-grep, no stray 42/41) ✅; the new MOUNTS guard has real teeth (`set(MOUNTS)==set(live paths)`) ✅.
- **architect LIVE HTTP (post-restart — main.py not hot-reloaded):** /mcp/tracing/mcp handshake→200 (session-mgr run + DNS-off for the new mount); tools/list→tracing_overview+tracing_log; tracing_overview structuredContent == GET /tracing data EXACTLY; **write-through round-trip on a THROWAWAY activity** — log val=4→4.0/pct40/not-done; log val=7 SAME DAY→ACCUMULATE 11.0/pct100/done/streak1; unknown→found:false (isError:false); val<0→isError:true; **throwaway ARCHIVED (no prod pollution)** — overview back to [].
- **team-lead independent LIVE HTTP:** read-side parity confirmed (tracing_overview.structuredContent == GET /tracing .data; honest-empty holds on MCP). Write-side relied on architect's throwaway round-trip (correctly avoided polluting the user's real store — the test-writes-pollute-prod lesson).
- **backend-w3 evidence:** the dedicated test set (is-identity, byte-identical, accumulate, unknown, negative, no-mutate guards); FULL pytest **2008 passed / 0 failed / 0 errors** (262.95s, +14 from 1994); the MOUNTS gap fixed + guard test added.

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** /mcp/tracing handshake 200 live; REST≡MCP byte-identical (#24); registry mount (NO core edit beyond the 1 _MCP_MOUNTS line); existence-contract honest. ✅
- **Gate 2 (Function):** the distinguishing set (is-identity/byte-identical/accumulate/unknown/negative/no-mutate-gate); FULL suite 2008/0/0 (NOT "N passed" w/ rejections); mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + LIVE HTTP + backend evidence; the MOUNTS coverage gap caught (via live HTTP) + fixed structurally before commit; commit format; explicit staged-set verified (no template/data/.mcp/Instruction leak); commit format. ✅

## Assumptions (user-review)
- **per-domain lifeos-tracing MCP** (tracing_overview read ref-imported is-identity + tracing_log write-through, missing→found:False, no proposal gate — reversible single-user append). REST≡MCP. **How to change:** the tracing_server TOOLS.
- **MOUNTS-in-sync guard:** the http test now pins its mount-coverage list to main._MCP_MOUNTS (a future mount auto-fails the guard, not silently). **How to change:** the guard test.

## Notes
- #65 Phase 2 of 4. Per-domain MCP pattern (clone reminders_server, ref-import the read fn for is-identity). backend-w3 BUILT; architect committed (§3, sole serialized committer). The MOUNTS gap (a live-HTTP coverage hole caught by architect's own live verify, masked by a green suite) is now structurally closed for all future mounts. Next (auto-run): P3 FE (/tracing S14 — designed, dispatch ready) → P4 brief-wire → #65 DONE (mốc lớn) → #63 → #64.
