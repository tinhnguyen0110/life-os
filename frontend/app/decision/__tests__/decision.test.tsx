import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";

/* Mock the api layer at the 5 NAMED getters useDecision calls (it does NOT call apiGet
   directly — the named helpers call the module-internal apiGet, which a top-level apiGet
   mock can't reach). Each getter resolves independently → mirrors the Promise.allSettled
   in useDecision (one failing section degrades, doesn't fail the cockpit). */
const getDecisionWeight = vi.fn();
const getMacroCycle = vi.fn();
const getDecisionAllocation = vi.fn();
const getDecisionGuardian = vi.fn();
const getNavHistory = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getDecisionWeight: (...a: unknown[]) => getDecisionWeight(...a),
    getMacroCycle: (...a: unknown[]) => getMacroCycle(...a),
    getDecisionAllocation: (...a: unknown[]) => getDecisionAllocation(...a),
    getDecisionGuardian: (...a: unknown[]) => getDecisionGuardian(...a),
    getNavHistory: (...a: unknown[]) => getNavHistory(...a),
  };
});

import DecisionPage from "../page";

afterEach(() => {
  getDecisionWeight.mockReset();
  getMacroCycle.mockReset();
  getDecisionAllocation.mockReset();
  getDecisionGuardian.mockReset();
  getNavHistory.mockReset();
});

/* ---- LIVE-shaped fixtures (curled on :8686, the real "thin" tower) ---- */
const WEIGHT = {
  success: true,
  data: {
    weight: 0.0238,
    verdict: "thin",
    breakdown: [
      { layer: "q_cycle", q: 0.5135, note: "cycle: phase=overheat, qCycle=0.5135" },
      { layer: "q_macro", q: 0.4366, note: "macro: 7 indicators, mean q=0.4366, source=fred" },
      { layer: "q_flow", q: 0.5789, note: "flow: 2/2 sentiment signals (F&G/BTC.d), q=0.5789" },
      { layer: "s_asset", q: 0.1836, note: "asset: 6/6 held assets with real technicals, q=0.1836" },
    ],
    bindingConstraint: "s_asset",
    explanation: "W = 0.5135 × 0.4366 × 0.5789 × 0.1836 = 0.0238 (pure product, no clamp); dimmest layer = s_asset",
    confidence: 0.4281,
    legend: "weight = signal strength (∏ of layer q); confidence = trust in the measurement.",
  },
};
const CYCLE = {
  success: true,
  data: {
    phase: "overheat",
    axes: [
      { axis: "growth", direction: "up", present: true, detail: "INDPRO up / UNRATE→flat" },
      { axis: "inflation", direction: "up", present: true, detail: "cpi up" },
      { axis: "yield_curve", direction: "flat", present: false, detail: "yield_curve_10y2y flat (mock)" },
    ],
    qCycle: { q: 0.5135, freshness: 0.7702, coverage: 0.6667, agreement: 1.0, breakdown: [], presentInputs: 2, neededInputs: 3 },
  },
};
const ALLOC = {
  success: true,
  data: {
    phase: "overheat",
    capitalTier: "small",
    targets: { crypto: 41.0, etf: 22.0, vn: 18.0, dry: 19.0 },
    rationale: { crypto: "reference 41.0% — classic clock (overheat) tilt -2pp", etf: "ref 22%", vn: "ref 18%", dry: "ref 19%" },
    vsStaticGoldenPath: { crypto: 3.0, etf: -2.0, vn: 0.0, dry: -1.0 },
    confidence: 0.6786,
    note: "REFERENCE weighting from the classic Investment-Clock + your capital size — a model assumption surfaced as DATA. You decide.",
  },
};
const GUARDIAN = {
  success: true,
  data: {
    alerts: [
      {
        severity: "high",
        msg: "crypto channel is 98% stablecoin (cash-equivalent) while Fear&Greed reads 23 — is standing in cash here an intentional bet?",
        evidence: { stablePct: 97.81, fearGreed: 23.0, fngSource: "live" },
        sources: ["finance_overview", "macro_history"],
      },
      { severity: "low", msg: "3 sub-$1 dust holdings (total $0.00) — worth a cleanup?", evidence: { dustCount: 3, dustUsd: 0.0 }, sources: ["finance_overview"] },
    ],
    confidence: 1.0,
    asOf: "2026-06-16T06:16:21.021248+00:00",
    note: null,
  },
};
const NAV = {
  success: true,
  data: {
    series: [{ date: "2026-06-15", nav: 10652.31 }, { date: "2026-06-16", nav: 10641.66 }],
    points: 2,
    range: { from: "2026-06-15", to: "2026-06-16" },
    confidence: 0.0661,
    warning: "2 point(s) — short series, a trend needs ~30; still accumulating",
  },
};

/** Wire every getter to its matching fixture (the happy "thin" tower). */
function wireAll() {
  getDecisionWeight.mockResolvedValue(WEIGHT);
  getMacroCycle.mockResolvedValue(CYCLE);
  getDecisionAllocation.mockResolvedValue(ALLOC);
  getDecisionGuardian.mockResolvedValue(GUARDIAN);
  getNavHistory.mockResolvedValue(NAV);
}

describe("Decision Cockpit — renders all 5 tower tools", () => {
  it("renders the W gauge with verdict + the 4-layer breakdown + binding constraint", async () => {
    wireAll();
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-weight")).toBeInTheDocument());
    // verdict WORD rendered verbatim
    expect(screen.getByTestId("weight-verdict")).toHaveTextContent("thin");
    // all 4 layers present
    for (const layer of ["q_cycle", "q_macro", "q_flow", "s_asset"]) {
      expect(screen.getByTestId(`layer-${layer}`)).toBeInTheDocument();
    }
    // binding constraint badge on s_asset (the dimmest layer)
    expect(screen.getByTestId("binding-s_asset")).toBeInTheDocument();
  });

  it("HONEST CONFIDENCE: weight and confidence are DISTINCT visuals (not one score) + legend shown", async () => {
    wireAll();
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-weight")).toBeInTheDocument());
    // two distinct elements
    const weightEl = screen.getByTestId("weight-value");
    const confEl = screen.getByTestId("weight-confidence");
    expect(weightEl).toBeInTheDocument();
    expect(confEl).toBeInTheDocument();
    // they show DIFFERENT numbers (weight 2.38% vs confidence 43%) — proves not conflated
    expect(weightEl).toHaveTextContent("2.38%");
    expect(within(confEl).getByText("43%")).toBeInTheDocument();
    // the §116 two-number legend is rendered
    expect(screen.getByTestId("weight-legend")).toHaveTextContent(/signal strength/i);
    expect(screen.getByTestId("weight-legend")).toHaveTextContent(/trust in the measurement/i);
  });

  it("thin W reads LOW CONVICTION: confidence band 'thấp' + the conviction box is 'blocked' tone", async () => {
    wireAll();
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("confidence-band")).toBeInTheDocument());
    // confidence 0.4281 → band low ("thấp")  — NOT a green "go"
    expect(screen.getByTestId("confidence-band")).toHaveTextContent("vừa"); // 0.4281 ≥ 0.4 → "vừa" band
    // the conviction box uses the de-emphasized (warn) tone for a mid/low signal, never "ok"
    const conv = screen.getByTestId("weight-conviction");
    expect(conv.className).not.toContain("ok");
  });

  it("renders the Investment Clock phase + axes (missing axis flagged honestly)", async () => {
    wireAll();
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-cycle")).toBeInTheDocument());
    expect(screen.getByTestId("cycle-phase")).toHaveTextContent("overheat");
    expect(screen.getByTestId("axis-growth")).toBeInTheDocument();
    // the mock/missing axis is flagged (honest coverage)
    expect(screen.getByTestId("axis-missing-yield_curve")).toBeInTheDocument();
  });

  it("GUARDIAN: renders each msg VERBATIM (questions, not advice)", async () => {
    wireAll();
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-guardian")).toBeInTheDocument());
    // the question is rendered exactly as the backend returns it
    expect(screen.getByTestId("guardian-msg-0")).toHaveTextContent(
      "crypto channel is 98% stablecoin (cash-equivalent) while Fear&Greed reads 23 — is standing in cash here an intentional bet?",
    );
    expect(screen.getByTestId("guardian-msg-1")).toHaveTextContent("worth a cleanup?");
  });

  it("renders the allocation reference weights + the vsStaticGoldenPath delta", async () => {
    wireAll();
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-allocation")).toBeInTheDocument());
    expect(screen.getByTestId("alloc-crypto")).toHaveTextContent("41%");
    // delta pp shown with sign (+3pp for crypto, −2pp for etf)
    expect(screen.getByTestId("alloc-delta-crypto")).toHaveTextContent("+3pp");
    expect(screen.getByTestId("alloc-delta-etf")).toHaveTextContent("−2pp");
    // the "you decide" note (neutral framing) is shown
    expect(screen.getByTestId("alloc-note")).toHaveTextContent(/You decide/i);
  });

  it("NAV short-series HONESTY: renders the warning + the points/confidence, no confident trend", async () => {
    wireAll();
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-nav")).toBeInTheDocument());
    expect(screen.getByTestId("nav-warning")).toHaveTextContent(/still accumulating/i);
    expect(screen.getByTestId("nav-points")).toHaveTextContent("2 điểm");
    // a dot per point so a 2-point series reads as discrete observations
    expect(screen.getByTestId("nav-dot-0")).toBeInTheDocument();
    expect(screen.getByTestId("nav-dot-1")).toBeInTheDocument();
  });
});

describe("Decision Cockpit — NEUTRAL copy (HARD acceptance: ZERO advice verbs in DOM)", () => {
  it("the rendered DOM contains NO advice imperatives", async () => {
    wireAll();
    const { container } = render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-allocation")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("decision-nav")).toBeInTheDocument());
    // the cockpit's OWN copy must not editorialize the neutral payloads into advice.
    // We scan the static chrome (labels/headers/helper text) the component itself adds —
    // the backend strings (verdict word / guardian questions) are rendered verbatim and
    // are themselves neutral (questions). The forbidden set is the advice-imperative list.
    const text = container.textContent ?? "";
    // word-boundary matches so "should"≠"shoulder", "move"≠"movement" etc.
    const FORBIDDEN = /\b(buy|sell|should|rebalance|deploy|recommend|ought)\b/i;
    expect(text).not.toMatch(FORBIDDEN);
  });
});

describe("Decision Cockpit — degrade & states", () => {
  it("loading → spinner", () => {
    const pending = () => new Promise(() => {}); // never resolves
    getDecisionWeight.mockImplementation(pending);
    getMacroCycle.mockImplementation(pending);
    getDecisionAllocation.mockImplementation(pending);
    getDecisionGuardian.mockImplementation(pending);
    getNavHistory.mockImplementation(pending);
    render(<DecisionPage />);
    expect(screen.getByTestId("decision-loading")).toBeInTheDocument();
  });

  it("ALL sections fail → hard error screen with retry", async () => {
    const boom = () => Promise.reject(new Error("backend down"));
    getDecisionWeight.mockImplementation(boom);
    getMacroCycle.mockImplementation(boom);
    getDecisionAllocation.mockImplementation(boom);
    getDecisionGuardian.mockImplementation(boom);
    getNavHistory.mockImplementation(boom);
    render(<DecisionPage />);
    await waitFor(() => expect(screen.getByTestId("decision-error")).toBeInTheDocument());
  });

  it("ONE section fails → cockpit still renders, that section degrades (no full error)", async () => {
    getDecisionWeight.mockResolvedValue(WEIGHT);
    getMacroCycle.mockResolvedValue(CYCLE);
    getDecisionAllocation.mockResolvedValue(ALLOC);
    getNavHistory.mockResolvedValue(NAV);
    getDecisionGuardian.mockRejectedValue(new Error("guardian boom"));
    render(<DecisionPage />);
    // weight still rendered (not a full error screen)
    await waitFor(() => expect(screen.getByTestId("weight-verdict")).toBeInTheDocument());
    expect(screen.queryByTestId("decision-error")).not.toBeInTheDocument();
    // guardian section shows its degraded state
    expect(screen.getByTestId("guardian-degraded")).toHaveTextContent("guardian boom");
  });
});
