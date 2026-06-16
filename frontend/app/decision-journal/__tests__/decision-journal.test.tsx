import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

const getDecisionJournal = vi.fn();
const createDecision = vi.fn();
const updateDecision = vi.fn();
const deleteDecision = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getDecisionJournal: (...a: unknown[]) => getDecisionJournal(...a),
    createDecision: (...a: unknown[]) => createDecision(...a),
    updateDecision: (...a: unknown[]) => updateDecision(...a),
    deleteDecision: (...a: unknown[]) => deleteDecision(...a),
  };
});

import DecisionJournalPage from "../page";
import { ApiError } from "@/lib/api";
import type { DecisionJournalData, DecisionEntry } from "@/lib/types";

function ok<T>(data: T) { return { success: true, data }; }
function entry(over: Partial<DecisionEntry>): DecisionEntry {
  return {
    id: "d1", decision: "Buy BTC", thesis: "halving rally", falsificationCondition: "below 50k",
    confidence: 70, predicted: null, date: "2026-06-15", domain: "investment",
    status: "open", outcome: null, lesson: null, createdAt: "x", updatedAt: "y", ...over,
  };
}
const DATA = (over: Partial<DecisionJournalData> = {}): DecisionJournalData => ({
  entries: [entry({})],
  count: 1, resolvedCount: 0, brier: null, calibration: [], biasFlags: [], ...over,
});

describe("Decision Journal (F1-H1)", () => {
  it("renders entries + backend stats (count/brier/bands/bias)", async () => {
    getDecisionJournal.mockResolvedValueOnce(ok(DATA({
      resolvedCount: 1, brier: 0.09,
      calibration: [{ band: "70-79", predicted: 74.5, actual: 100, n: 1 }],
      biasFlags: [{ domain: "project", wrongRate: 0.75, n: 4 }],
      entries: [entry({ status: "resolved", outcome: "right" })],
    })));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    expect(screen.getByTestId("dj-stats")).toHaveTextContent("0.090"); // brier rendered
    expect(screen.getByTestId("dj-calibration")).toBeInTheDocument();
    expect(screen.getByTestId("dj-band")).toHaveTextContent("70-79");
    expect(screen.getByTestId("dj-bias-flag")).toHaveTextContent("project");
  });

  it("Brier null (0 resolved) → shows '—', NOT a fabricated number", async () => {
    getDecisionJournal.mockResolvedValueOnce(ok(DATA({ brier: null, resolvedCount: 0 })));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-stats")).toBeInTheDocument());
    expect(screen.getByTestId("dj-stats")).toHaveTextContent("—");
    expect(screen.queryByTestId("dj-calibration")).toBeNull(); // no bands when empty
  });

  it("create a decision → calls createDecision with parsed fields", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    createDecision.mockResolvedValueOnce(ok(entry({})));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-toggle-create"));
    fireEvent.change(screen.getByTestId("dj-decision"), { target: { value: "Ship feature X" } });
    fireEvent.change(screen.getByTestId("dj-domain"), { target: { value: "project" } });
    fireEvent.change(screen.getByTestId("dj-confidence"), { target: { value: "80" } });
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(createDecision).toHaveBeenCalled());
    const arg = createDecision.mock.calls[0][0];
    expect(arg).toMatchObject({ decision: "Ship feature X", domain: "project", confidence: 80 });
  });

  it("EV/worst-case core: the 3 fields (expectedEv/worstCase/decisionWeight) POST through", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    createDecision.mockResolvedValueOnce(ok(entry({})));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-toggle-create"));
    fireEvent.change(screen.getByTestId("dj-decision"), { target: { value: "Bet at W=0.0238" } });
    fireEvent.change(screen.getByTestId("dj-domain"), { target: { value: "investment" } });
    fireEvent.change(screen.getByTestId("dj-confidence"), { target: { value: "55" } });
    fireEvent.change(screen.getByTestId("dj-expectedEv"), { target: { value: "positive_asymmetric" } });
    fireEvent.change(screen.getByTestId("dj-worstCase"), { target: { value: "lose 100% of position" } });
    fireEvent.change(screen.getByTestId("dj-decisionWeight"), { target: { value: "0.0238" } });
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(createDecision).toHaveBeenCalled());
    const arg = createDecision.mock.calls[0][0];
    expect(arg).toMatchObject({
      decision: "Bet at W=0.0238",
      expectedEv: "positive_asymmetric",
      worstCase: "lose 100% of position",
      decisionWeight: 0.0238,
    });
  });

  it("the 3 EV/worst-case fields are OPTIONAL — omitted when blank (not sent as empty)", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    createDecision.mockResolvedValueOnce(ok(entry({})));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-toggle-create"));
    fireEvent.change(screen.getByTestId("dj-decision"), { target: { value: "no-EV decision" } });
    fireEvent.change(screen.getByTestId("dj-domain"), { target: { value: "project" } });
    fireEvent.change(screen.getByTestId("dj-confidence"), { target: { value: "60" } });
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(createDecision).toHaveBeenCalled());
    const arg = createDecision.mock.calls[0][0];
    // blank optional fields are NOT in the payload (backend defaults None) — never sent as ""
    expect(arg).not.toHaveProperty("expectedEv");
    expect(arg).not.toHaveProperty("worstCase");
    expect(arg).not.toHaveProperty("decisionWeight");
  });

  it("decisionWeight out of 0–1 range → client-blocked, never hits the API", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-toggle-create"));
    fireEvent.change(screen.getByTestId("dj-decision"), { target: { value: "X" } });
    fireEvent.change(screen.getByTestId("dj-domain"), { target: { value: "investment" } });
    fireEvent.change(screen.getByTestId("dj-confidence"), { target: { value: "60" } });
    fireEvent.change(screen.getByTestId("dj-decisionWeight"), { target: { value: "1.5" } }); // > 1
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(screen.getByTestId("dj-form-error")).toHaveTextContent(/0–1/));
    expect(createDecision).not.toHaveBeenCalled();
  });

  it("FAIL-CLOSED: create 422 → error surfaced in form, not swallowed", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    createDecision.mockRejectedValueOnce(new ApiError(422, "confidence: must be 0-100"));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-toggle-create"));
    fireEvent.change(screen.getByTestId("dj-decision"), { target: { value: "X" } });
    fireEvent.change(screen.getByTestId("dj-domain"), { target: { value: "project" } });
    fireEvent.change(screen.getByTestId("dj-confidence"), { target: { value: "80" } });
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(screen.getByTestId("dj-form-error")).toHaveTextContent("0-100"));
  });

  it("client-validates confidence range before hitting the API", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-toggle-create"));
    fireEvent.change(screen.getByTestId("dj-decision"), { target: { value: "X" } });
    fireEvent.change(screen.getByTestId("dj-domain"), { target: { value: "project" } });
    fireEvent.change(screen.getByTestId("dj-confidence"), { target: { value: "150" } }); // out of range
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(screen.getByTestId("dj-form-error")).toBeInTheDocument());
    expect(createDecision).not.toHaveBeenCalled(); // never hit the API
  });

  it("optional predicted field → sent only when set, validated 0–1", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    createDecision.mockResolvedValue(ok(entry({})));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-toggle-create"));
    fireEvent.change(screen.getByTestId("dj-decision"), { target: { value: "X" } });
    fireEvent.change(screen.getByTestId("dj-domain"), { target: { value: "project" } });
    fireEvent.change(screen.getByTestId("dj-confidence"), { target: { value: "80" } });
    // out-of-range predicted → client-blocked
    fireEvent.change(screen.getByTestId("dj-predicted"), { target: { value: "5" } });
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(screen.getByTestId("dj-form-error")).toHaveTextContent("0–1"));
    expect(createDecision).not.toHaveBeenCalled();
    // valid predicted → included in payload
    fireEvent.change(screen.getByTestId("dj-predicted"), { target: { value: "0.85" } });
    fireEvent.click(screen.getByTestId("dj-create-submit"));
    await waitFor(() => expect(createDecision).toHaveBeenCalled());
    expect(createDecision.mock.calls[0][0]).toMatchObject({ predicted: 0.85 });
  });

  it("resolve an open decision → updateDecision({status:resolved, outcome})", async () => {
    getDecisionJournal.mockResolvedValue(ok(DATA()));
    updateDecision.mockResolvedValueOnce(ok(entry({ status: "resolved", outcome: "wrong" })));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("dj-resolve-d1"));
    await waitFor(() => expect(screen.getByTestId("dj-resolve-panel")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("dj-resolve-outcome"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByTestId("dj-resolve-submit"));
    await waitFor(() => expect(updateDecision).toHaveBeenCalledWith("d1", expect.objectContaining({ status: "resolved", outcome: "wrong" })));
  });

  it("empty journal → honest empty state (DataTable empty), no fabricated rows", async () => {
    getDecisionJournal.mockResolvedValueOnce(ok(DATA({ entries: [], count: 0 })));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-list")).toBeInTheDocument());
    expect(screen.getByTestId("datatable-empty")).toBeInTheDocument();
  });

  it("loading then error surfaces", async () => {
    getDecisionJournal.mockRejectedValueOnce(new Error("down"));
    render(<DecisionJournalPage />);
    await waitFor(() => expect(screen.getByTestId("dj-error")).toBeInTheDocument());
    expect(screen.getByTestId("dj-error")).toHaveTextContent("down");
  });
});
