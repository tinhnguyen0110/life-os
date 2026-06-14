/**
 * router-isolation.guard.test.tsx — Sprint 0A test-isolation regression guard.
 *
 * PURPOSE (mirrors the backend sys.modules tripwire): prove that a shell
 * component which uses navigation does NOT silently depend on a `next/navigation`
 * (or `@/lib/useNav`) mock bleeding in from another test file. If cross-file
 * mock isolation is ever dropped — or the `useSafeRouter`/`useSafePathname`
 * fallback in `@/lib/useNav` is removed — this file goes RED on its own.
 *
 * WHY THIS SHAPE (not "expect a throw"): TopBar deliberately reads router/path
 * via the safe wrappers in `@/lib/useNav`, which degrade to a no-op router and
 * "/" pathname when NO AppRouter provider is mounted (the jsdom unit case).
 * So the correct, architecture-true assertion is: it renders cleanly AND falls
 * back to the Home crumb — NOT that it crashes.
 *
 * DELIBERATELY UNMOCKED: next/navigation and @/lib/useNav. This file mounts
 * TopBar with ZERO navigation mocks, so it cannot benefit from any leak.
 * ONLY @/lib/api.getHealth is stubbed — that is an external network boundary,
 * not the navigation contract under test.
 *
 * If a future sprint adds a top-level `vi.mock("next/navigation")` or
 * `vi.mock("@/lib/useNav")` to THIS file, it defeats the guard — don't.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, cleanup, act } from "@testing-library/react";

// TopBar fetches on mount (getHealth + getRoutines). These guard tests assert
// synchronously, so the resolved state lands after the test → a React act() warning.
// Flushing pending microtasks/effects inside act() settles it (no behaviour change).
async function flushEffects() {
  await act(async () => { await Promise.resolve(); });
}

// Stub ONLY the network boundary. Navigation is intentionally left real so the
// safe-wrapper fallback is the thing actually exercised.
const getHealth = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getHealth: () => getHealth() };
});

import { TopBar } from "../TopBar";

describe("router-isolation guard (no next/navigation or useNav mock)", () => {
  beforeEach(() => {
    getHealth.mockReset();
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    cleanup();
  });

  it("TopBar renders without throwing when NO AppRouter provider is mounted", async () => {
    // If the safe-wrapper fallback (useNav) were removed, next/navigation's
    // useRouter()/usePathname() invariant would throw here — turning this RED.
    expect(() => render(<TopBar />)).not.toThrow();
    await flushEffects();
  });

  it("falls back to the Home crumb ('/') when no router/path context exists", async () => {
    // useSafePathname() → "/" with no PathnameContext → crumbFor("/") === "Home".
    // A leaked mock that pinned pathname to some other route would break this,
    // exposing the cross-file bleed.
    render(<TopBar />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Home");
    await flushEffects();
  });

  it("still drives its own state (API pill) without any navigation mock", async () => {
    render(<TopBar />);
    await waitFor(() =>
      expect(screen.getByTestId("api-pill")).toHaveTextContent("live"),
    );
  });

  it("the bell click is a no-op router push (does not throw) without a provider", async () => {
    // useSafeRouter() → NOOP_ROUTER.push when unmounted. Clicking the bell must
    // not crash — proving the no-op fallback, not a leaked mock, is in effect.
    render(<TopBar />);
    expect(() => screen.getByLabelText("Cảnh báo").click()).not.toThrow();
    await flushEffects();
  });
});
