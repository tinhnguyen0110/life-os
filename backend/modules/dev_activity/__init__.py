"""modules/dev_activity/ — local git dev-activity tracing (Cairn #63 Phase 1).

Scans the user's LOCAL git repos (no credentials) → per (date-VN × repo × source) commits + LOC
(filtered) + active-span. PORTS the proven validate_dev_tracing.py local_probe logic (LOC_SKIP,
--no-merges, identity-map, TZ-VN) — zero invention. LOC is INFORMATIONAL (Goodhart — never a score/
rank); commits + active-span + by-repo distribution are the primary signals. P1 = local-scan only;
P2 = remote (GitHub/Bitbucket + cred), P3 = FE + brief-wire. The registry auto-discovers MODULE.
"""
