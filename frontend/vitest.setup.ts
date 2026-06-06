import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { vi } from "vitest";

/* ============================================================
   Sprint 0A — global test isolation (mirrors backend sys.modules tripwire).
   Without this, two failure modes leak ACROSS tests/files:
     1. Rendered DOM accumulates (jsdom not unmounted) → stale nodes, dup queries.
     2. vi.fn() call history / mock impls persist → a stateful mock value set in
        test A (e.g. `let mockPath = "/market"`, or a `mockResolvedValueOnce`)
        bleeds into test B, which then asserts against A's leftover state.
   `cleanup()` unmounts React trees; `vi.clearAllMocks()` resets every mock's
   call history + one-shot impls. NOTE: clearAllMocks does NOT remove module
   factories registered via `vi.mock(...)` — those are intentionally per-file and
   must stay; it only wipes per-mock state, which is the real cross-test leak.
   The guard in `components/__tests__/isolation.guard.test.tsx` proves this is
   load-bearing: strip these lines and it goes RED.
   ============================================================ */
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
