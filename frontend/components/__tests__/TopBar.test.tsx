import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const push = vi.fn();
let mockPath = "/market";
vi.mock("@/lib/useNav", () => ({
  useSafeRouter: () => ({ push }),
  useSafePathname: () => mockPath,
}));

const getHealth = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getHealth: () => getHealth() };
});

import { TopBar } from "../TopBar";

describe("TopBar", () => {
  beforeEach(() => {
    push.mockClear();
    getHealth.mockReset();
  });

  it("shows breadcrumb for the current route", async () => {
    mockPath = "/market";
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Thị trường & Cảnh báo");
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
  });

  it("detail route falls back to the parent breadcrumb", async () => {
    mockPath = "/projects/foo";
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Dự án");
  });
});
