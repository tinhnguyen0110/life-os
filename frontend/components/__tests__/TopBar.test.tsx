import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const push = vi.fn();
let mockPath = "/market";
vi.mock("@/lib/useNav", () => ({
  useSafeRouter: () => ({ push }),
  useSafePathname: () => mockPath,
}));

const getHealth = vi.fn();
const getRoutines = vi.fn();
const verifyPrivacyPass = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getHealth: () => getHealth(),
    getRoutines: () => getRoutines(),
    // #74 change 5: mock the NAMED verify helper (usePrivacy.unlock calls it) — NOT
    // apiGet/apiPost (module-closure: a low-level mock won't intercept the named call).
    verifyPrivacyPass: (...a: unknown[]) => verifyPrivacyPass(...a),
  };
});

import { TopBar } from "../TopBar";

// TopBar fires two async fetches on mount (getHealth → api-pill, getRoutines →
// routine-active-pill). Tests that assert synchronously must still let BOTH settle
// or React logs an act() warning when the state lands after the test. waitFor
// retries inside act() until the api-pill leaves its initial "checking" label —
// by then both mounted-effect promises have flushed.
async function settleTopBar() {
  await waitFor(() => expect(screen.getByTestId("api-pill")).not.toHaveTextContent("checking"));
}

describe("TopBar", () => {
  beforeEach(() => {
    push.mockClear();
    getHealth.mockReset();
    getRoutines.mockReset();
    verifyPrivacyPass.mockReset();
    getRoutines.mockResolvedValue({ success: true, data: { routines: [], activeCount: 3, total: 4, runsToday: 0, lastRunAt: null } });
    localStorage.clear();
    document.body.removeAttribute("data-privacy");
  });
  afterEach(() => {
    cleanup();
    localStorage.clear();
    document.body.removeAttribute("data-privacy");
  });

  it("routine-active pill shows the LIVE activeCount (wired to /routines)", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar route="Home" />);
    await waitFor(() => expect(screen.getByTestId("routine-active-pill")).toHaveTextContent("3 routine active"));
  });

  it("routine pill fails soft → '—', does not crash the TopBar", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    getRoutines.mockRejectedValueOnce(new Error("down"));
    render(<TopBar route="Home" />);
    await waitFor(() => expect(screen.getByTestId("routine-active-pill")).toHaveTextContent("— routine active"));
  });

  it("shows breadcrumb for the current route", async () => {
    mockPath = "/market";
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Thị trường & Cảnh báo");
    await settleTopBar();
  });

  it("API pill goes live when /health succeeds", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    await waitFor(() => expect(screen.getByTestId("api-pill")).toHaveTextContent("live"));
  });

  it("API pill goes down when /health rejects (backend not up — no crash)", async () => {
    getHealth.mockRejectedValue(new Error("ECONNREFUSED"));
    render(<TopBar />);
    await waitFor(() => expect(screen.getByTestId("api-pill")).toHaveTextContent("down"));
  });

  it("bell navigates to /market", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    screen.getByLabelText("Cảnh báo").click();
    expect(push).toHaveBeenCalledWith("/market");
    await settleTopBar();
  });

  it("detail route falls back to the parent breadcrumb", async () => {
    mockPath = "/projects/foo";
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Dự án");
    await settleTopBar();
  });

  // #74 change 3 + 5 — privacy toggle on the TopBar; ON hides money (locked) + a pass
  // modal reveals it (POST /settings/privacy/verify).
  describe("privacy toggle + reveal-pass modal", () => {
    async function readyTopBar() {
      getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
      render(<TopBar route="Home" />);
      await waitFor(() => expect(screen.getByTestId("tb-privacy-toggle")).toBeInTheDocument());
    }

    it("renders the toggle in the TopBar right cluster (default OFF, money shown)", async () => {
      await readyTopBar();
      expect(screen.getByTestId("tb-privacy-toggle")).toHaveAttribute("data-privacy-on", "0");
      expect(document.body.hasAttribute("data-privacy")).toBe(false);
      await settleTopBar();
    });

    it("OFF → click turns ON + LOCKS (body[data-privacy=on], money masked) + persists", async () => {
      const user = userEvent.setup();
      await readyTopBar();
      await user.click(screen.getByTestId("tb-privacy-toggle"));
      // ON + locked → the mask body attr is set (••••)
      await waitFor(() => expect(document.body.getAttribute("data-privacy")).toBe("on"));
      expect(screen.getByTestId("tb-privacy-toggle")).toHaveAttribute("data-privacy-locked", "1");
      // persisted device-local
      expect(localStorage.getItem("lifeos.privacy")).toBe(JSON.stringify({ on: true }));
      await settleTopBar();
    });

    it("ON+locked → click opens the reveal MODAL (does NOT just toggle off)", async () => {
      const user = userEvent.setup();
      await readyTopBar();
      await user.click(screen.getByTestId("tb-privacy-toggle")); // ON + locked
      await waitFor(() => expect(document.body.getAttribute("data-privacy")).toBe("on"));
      await user.click(screen.getByTestId("tb-privacy-toggle")); // → modal
      await waitFor(() => expect(screen.getByTestId("privacy-modal")).toBeInTheDocument());
      // still locked (modal open, not yet revealed)
      expect(document.body.getAttribute("data-privacy")).toBe("on");
      await settleTopBar();
    });

    it("right pass → data.ok=true → UNLOCKS (money shown), modal closes", async () => {
      verifyPrivacyPass.mockResolvedValue({ success: true, data: { ok: true } });
      const user = userEvent.setup();
      await readyTopBar();
      await user.click(screen.getByTestId("tb-privacy-toggle")); // lock
      await waitFor(() => expect(document.body.getAttribute("data-privacy")).toBe("on"));
      await user.click(screen.getByTestId("tb-privacy-toggle")); // open modal
      await user.type(screen.getByTestId("privacy-modal-input"), "0110");
      await user.click(screen.getByTestId("privacy-modal-submit"));
      // verify called with the attempt (NOT the pass hardcoded in FE)
      await waitFor(() => expect(verifyPrivacyPass).toHaveBeenCalledWith("0110"));
      // unlocked → body mask removed (money shows) + modal closed
      await waitFor(() => expect(document.body.hasAttribute("data-privacy")).toBe(false));
      expect(screen.queryByTestId("privacy-modal")).toBeNull();
      // privacy is STILL on (eye 🙈) — unlocked, not off
      expect(screen.getByTestId("tb-privacy-toggle")).toHaveAttribute("data-privacy-on", "1");
      await settleTopBar();
    });

    it("wrong pass → data.ok=false → 'Sai mã' error in modal, STAYS hidden", async () => {
      verifyPrivacyPass.mockResolvedValue({ success: true, data: { ok: false } });
      const user = userEvent.setup();
      await readyTopBar();
      await user.click(screen.getByTestId("tb-privacy-toggle")); // lock
      await user.click(screen.getByTestId("tb-privacy-toggle")); // modal
      await user.type(screen.getByTestId("privacy-modal-input"), "9999");
      await user.click(screen.getByTestId("privacy-modal-submit"));
      await waitFor(() => expect(screen.getByTestId("privacy-modal-error")).toHaveTextContent(/Sai mã/i));
      // still masked, modal still open
      expect(document.body.getAttribute("data-privacy")).toBe("on");
      expect(screen.getByTestId("privacy-modal")).toBeInTheDocument();
      await settleTopBar();
    });

    // FOLLOW-UP BUG FIX: ON+unlocked → click RE-HIDES in ONE click (was: turned privacy
    // OFF, needing a 2nd click to re-hide). privacy stays ON, money masks again.
    it("ON+unlocked → ONE click RE-HIDES money (single-click re-hide, the bug fix)", async () => {
      verifyPrivacyPass.mockResolvedValue({ success: true, data: { ok: true } });
      const user = userEvent.setup();
      await readyTopBar();
      await user.click(screen.getByTestId("tb-privacy-toggle")); // lock
      await user.click(screen.getByTestId("tb-privacy-toggle")); // modal
      await user.type(screen.getByTestId("privacy-modal-input"), "0110");
      await user.click(screen.getByTestId("privacy-modal-submit"));
      await waitFor(() => expect(document.body.hasAttribute("data-privacy")).toBe(false)); // unlocked/shown
      // ONE click → money HIDDEN again (re-locked), privacy STILL on (not turned off)
      await user.click(screen.getByTestId("tb-privacy-toggle"));
      await waitFor(() => expect(document.body.getAttribute("data-privacy")).toBe("on"));
      expect(screen.getByTestId("tb-privacy-toggle")).toHaveAttribute("data-privacy-on", "1"); // privacy still ON
      expect(screen.getByTestId("tb-privacy-toggle")).toHaveAttribute("data-privacy-locked", "1"); // re-locked
      await settleTopBar();
    });

    it("the reveal modal's 'Tắt' button turns privacy fully OFF (money normal, un-armed)", async () => {
      const user = userEvent.setup();
      await readyTopBar();
      await user.click(screen.getByTestId("tb-privacy-toggle")); // lock
      await user.click(screen.getByTestId("tb-privacy-toggle")); // open modal
      await waitFor(() => expect(screen.getByTestId("privacy-modal-turnoff")).toBeInTheDocument());
      await user.click(screen.getByTestId("privacy-modal-turnoff"));
      // privacy fully OFF: no mask, eye OFF, modal closed, persisted off
      await waitFor(() => expect(document.body.hasAttribute("data-privacy")).toBe(false));
      expect(screen.getByTestId("tb-privacy-toggle")).toHaveAttribute("data-privacy-on", "0");
      expect(screen.queryByTestId("privacy-modal")).toBeNull();
      expect(localStorage.getItem("lifeos.privacy")).toBe(JSON.stringify({ on: false }));
      await settleTopBar();
    });
  });
});
