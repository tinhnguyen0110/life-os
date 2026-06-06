import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/useNav", () => ({ useSafeRouter: () => ({ push: vi.fn() }) }));

const getSettings = vi.fn();
const patchSettings = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getSettings: () => getSettings(), patchSettings: (...a: unknown[]) => patchSettings(...a) };
});

import SettingsPage from "../page";
import { ApiError } from "@/lib/api";

afterEach(() => { getSettings.mockReset(); patchSettings.mockReset(); });

// mirrors the reconciled GET /settings truth: timezone=Asia/Ho_Chi_Minh, displayName="" (blank VALID — no min-length).
const CONFIG = (over = {}) => ({
  automationEnabled: true, briefHour: 8, idleThresholdDays: 7,
  patternCheckEnabled: true, errorChannel: "inapp", timezone: "Asia/Ho_Chi_Minh", displayName: "", ...over,
});
const ENV = (data: unknown) => ({ success: true, data });
// a real FastAPI per-field 422 for briefHour
const err422 = (field: string, msg: string) =>
  new ApiError(422, `${field}: ${msg}`, [{ type: "x", loc: ["body", field], msg }]);

describe("S12 Settings — render + states", () => {
  it("renders the 4 panels render-only from config", async () => {
    getSettings.mockResolvedValueOnce(ENV(CONFIG()));
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("settings-automation")).toBeInTheDocument());
    expect(screen.getByTestId("settings-account")).toBeInTheDocument();
    expect(screen.getByTestId("settings-integrations")).toBeInTheDocument();
    expect(screen.getByTestId("settings-api")).toBeInTheDocument();
    // master toggle reflects config (on)
    expect(screen.getByTestId("cfg-automationEnabled-toggle")).toHaveAttribute("aria-checked", "true");
    expect((screen.getByTestId("cfg-briefHour-input") as HTMLInputElement).value).toBe("8");
  });

  it("GET error → friendly error + retry", async () => {
    getSettings.mockRejectedValueOnce(new ApiError(0, "down"));
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("settings-error")).toBeInTheDocument());
  });

  it("TEETH: malformed body (data==null) → error, not blank", async () => {
    getSettings.mockResolvedValueOnce({ success: true, data: null });
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("settings-error")).toBeInTheDocument());
  });
});

describe("S12 Settings — write round-trip (fail-closed)", () => {
  it("edit briefHour + Lưu → PATCH then config from SERVER response (not optimistic)", async () => {
    getSettings.mockResolvedValue(ENV(CONFIG()));
    // server echoes the NEW config (briefHour 9) — we trust the server, not the local edit
    patchSettings.mockResolvedValueOnce(ENV(CONFIG({ briefHour: 9 })));
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("cfg-briefHour-input")).toBeInTheDocument());
    const input = screen.getByTestId("cfg-briefHour-input");
    await user.clear(input);
    await user.type(input, "9");
    await user.click(screen.getByTestId("cfg-briefHour-save"));
    await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ briefHour: 9 }));
    // server-confirmed value rendered
    await waitFor(() => expect((screen.getByTestId("cfg-briefHour-input") as HTMLInputElement).value).toBe("9"));
  });

  it("TEETH: 422 on briefHour → INLINE per-field error, value NOT silently applied (fail-closed)", async () => {
    getSettings.mockResolvedValue(ENV(CONFIG()));
    patchSettings.mockRejectedValueOnce(err422("briefHour", "Input should be less than or equal to 23"));
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("cfg-briefHour-input")).toBeInTheDocument());
    const input = screen.getByTestId("cfg-briefHour-input");
    await user.clear(input);
    await user.type(input, "99");
    await user.click(screen.getByTestId("cfg-briefHour-save"));
    // the per-field 422 message surfaces inline on THIS field
    await waitFor(() => expect(screen.getByTestId("cfg-briefHour-error")).toBeInTheDocument());
    expect(screen.getByTestId("cfg-briefHour-error")).toHaveTextContent(/less than or equal to 23/);
  });

  it("toggle flip → PATCH (save-on-flip, fail-closed)", async () => {
    getSettings.mockResolvedValue(ENV(CONFIG()));
    patchSettings.mockResolvedValueOnce(ENV(CONFIG({ automationEnabled: false })));
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("cfg-automationEnabled-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("cfg-automationEnabled-toggle"));
    await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ automationEnabled: false }));
    await waitFor(() => expect(screen.getByTestId("cfg-automationEnabled-toggle")).toHaveAttribute("aria-checked", "false"));
  });

  it("TEETH: toggle PATCH fails (non-422) → form error surfaces, fail-closed", async () => {
    getSettings.mockResolvedValue(ENV(CONFIG()));
    patchSettings.mockRejectedValueOnce(new ApiError(500, "server blew up"));
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("cfg-patternCheckEnabled-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("cfg-patternCheckEnabled-toggle"));
    await waitFor(() => expect(within(screen.getByTestId("settings-automation")).getByText(/server blew up/)).toBeInTheDocument());
  });

  it("displayName edit + Lưu → PATCH with the new name", async () => {
    getSettings.mockResolvedValue(ENV(CONFIG({ displayName: "Tinh" })));
    patchSettings.mockResolvedValueOnce(ENV(CONFIG({ displayName: "Khoa" })));
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("cfg-displayName-input")).toBeInTheDocument());
    const input = screen.getByTestId("cfg-displayName-input");
    await user.clear(input);
    await user.type(input, "Khoa");
    await user.click(screen.getByTestId("cfg-displayName-save"));
    await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ displayName: "Khoa" }));
  });

  it("TEETH: BLANK displayName is VALID — NO phantom client 'required' validator (PATCHes '', no inline error)", async () => {
    // backend has max_length only, NO min_length → "" submits 200. The FE must NOT
    // invent a required/min-length constraint the API doesn't enforce (S12 correction).
    getSettings.mockResolvedValue(ENV(CONFIG({ displayName: "Tinh" })));
    patchSettings.mockResolvedValueOnce(ENV(CONFIG({ displayName: "" })));
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("cfg-displayName-input")).toBeInTheDocument());
    await user.clear(screen.getByTestId("cfg-displayName-input")); // blank it
    await user.click(screen.getByTestId("cfg-displayName-save"));
    // PATCHes the empty string (no client-side block) ...
    await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ displayName: "" }));
    // ... and shows NO inline error (blank is legal)
    expect(screen.queryByTestId("cfg-displayName-error")).toBeNull();
  });
});

describe("S12 Settings — honest integration status (NO fake toggles)", () => {
  it("integrations show live/phase-2 BADGES, not toggles", async () => {
    getSettings.mockResolvedValueOnce(ENV(CONFIG()));
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("settings-integrations")).toBeInTheDocument());
    const panel = screen.getByTestId("settings-integrations");
    // GitHub + market feed = live; Claude MCP + Webhook = phase 2 (honest)
    expect(within(panel).getAllByText("live").length).toBeGreaterThanOrEqual(2);
    expect(within(panel).getAllByText("phase 2").length).toBeGreaterThanOrEqual(2);
    // NO toggle switches in the integrations panel (those would imply you can flip them)
    expect(within(panel).queryByRole("switch")).toBeNull();
  });

  it("Mở Tweaks is honest coming-soon (disabled, no theme system this build)", async () => {
    getSettings.mockResolvedValueOnce(ENV(CONFIG()));
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("open-tweaks")).toBeInTheDocument());
    expect(screen.getByTestId("open-tweaks")).toBeDisabled();
  });
});
