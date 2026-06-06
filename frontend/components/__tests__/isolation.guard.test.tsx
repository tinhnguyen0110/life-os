/**
 * isolation.guard.test.tsx — Sprint 0A test-isolation tripwire (FE mirror of the
 * backend sys.modules guard).
 *
 * WHAT IT GUARDS: the global `afterEach(() => { cleanup(); vi.clearAllMocks(); })`
 * wired in `vitest.setup.ts`. Without that cleanup, mock state (call history,
 * one-shot impls) and rendered DOM leak from one test into the next — the #1
 * cross-test flake. This file constructs that leak deliberately and asserts the
 * CLEAN state, so:
 *   - isolation ON  (setup intact)   → GREEN
 *   - isolation OFF (afterEach stripped) → RED (test 2 sees test 1's leaked call)
 *
 * HOW TO PROVE IT'S LOAD-BEARING: delete the afterEach block in vitest.setup.ts,
 * run `npx vitest run components/__tests__/isolation.guard.test.tsx` → test 2
 * (and the DOM-leak test) go RED. Restore → GREEN. (Done in Sprint 0A report.)
 *
 * This is NOT a contrived always-false assert: the failure is a REAL leaked
 * vi.fn() call count / a REAL un-unmounted DOM node surviving across tests.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// A module-level stateful mock fn — exactly the pattern real shell tests use
// (TopBar/Sidebar keep a `vi.fn()` push + a `let mockPath`). Its call history is
// the thing that must be cleared between tests.
const sharedSpy = vi.fn();

describe("test-isolation tripwire — mock call-history must not leak across tests", () => {
  // Order matters: this test runs FIRST and dirties the shared spy.
  it("test 1: dirties the shared mock (calls it once)", () => {
    sharedSpy("dirty");
    expect(sharedSpy).toHaveBeenCalledTimes(1);
  });

  // If afterEach(vi.clearAllMocks()) ran, this sees a CLEAN spy (0 calls).
  // If isolation is stripped, it sees test 1's leaked call (1) → RED.
  it("test 2: shared mock is clean (proves clearAllMocks ran between tests)", () => {
    expect(sharedSpy).toHaveBeenCalledTimes(0);
  });
});

describe("test-isolation tripwire — rendered DOM must not leak across tests", () => {
  // Renders a uniquely-identifiable node and leaves it mounted (no manual unmount).
  it("test 1: mounts a marker node", () => {
    render(<div data-testid="iso-marker">leak-check</div>);
    expect(screen.getAllByTestId("iso-marker")).toHaveLength(1);
  });

  // If cleanup() ran in afterEach, the previous render was unmounted → this fresh
  // render yields exactly ONE marker. If cleanup is stripped, jsdom keeps the old
  // node too → getAllByTestId returns 2 → RED.
  it("test 2: only the current render's marker exists (proves cleanup ran)", () => {
    render(<div data-testid="iso-marker">leak-check</div>);
    expect(screen.getAllByTestId("iso-marker")).toHaveLength(1);
  });
});
