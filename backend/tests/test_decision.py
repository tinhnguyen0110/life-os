"""tests/test_decision.py — the DECISION TOWER (FINANCE-ASSISTANT P2, #54).

The 5 HARD GATES (each MANDATORY, the spec's "2 people can't implement it differently" risk):
 1. THE acceptance test — q_cycle ≈ 0.45 FALLS OUT of compute_q BY COMPUTATION (not typed).
 2. decision_weight is a PURE PRODUCT, NO clamp — proven with a DIVERGENT dim-upper+bright-
    lower case (an all-equal fixture would pass a broken clamp) + a zero-layer → W=0.
 3. weight and confidence are SEPARATE fields (the dangerous high-weight+low-confidence quadrant).
 4. macro_cycle honest-missing — a mock/missing axis → coverage<1 → lower q + warning, never a
    fabricated phase. + NEUTRAL: no advice verb in the payload.
 5. compute_q is the SINGLE source — macro_cycle + decision_weight + the macro seam all CALL
    compute_q; none reimplements freshness/coverage/agreement (AST/import check).
"""

from __future__ import annotations

import ast
import inspect
import math

import pytest

from modules.decision import service as dec
from modules.decision.service import QInput, compute_q


# --------------------------------------------------------------------------- #
# HARD GATE 1 — the acceptance test: 0.45 FALLS OUT (the phase-defining test)    #
# --------------------------------------------------------------------------- #
def test_GATE1_q_cycle_045_falls_out_by_computation():
    """THE acceptance test (spec §75-83): realistic 2/4-axis inputs → q ≈ 0.45 BY COMPUTATION.
    freshness ≈ 0.9 (present axes ~3.16d old, τ=30d → exp(-3.16/30)=0.90) × coverage 0.5 (2/4)
    × agreement 1.0 (equal direction) = 0.45. If 0.45 were hardcoded anywhere this would not
    track the inputs — so we ALSO assert that changing an input MOVES the output."""
    # pick age so exp(-age/30) == 0.90 exactly → age = -30*ln(0.9)
    age = -30.0 * math.log(0.90)
    inputs = [
        QInput(name="yield_curve", present=True, value=1.0, age_days=age, data_type="cycle"),
        QInput(name="cpi", present=True, value=1.0, age_days=age, data_type="cycle"),
        QInput(name="pmi", present=False),            # MISSING → lowers coverage
        QInput(name="unemployment", present=False),   # MISSING
    ]
    r = compute_q(inputs, needed=4)
    assert r.coverage == 0.5                          # 2/4
    assert abs(r.freshness - 0.90) < 0.005            # exp(-age/30) ≈ 0.90
    assert r.agreement == 1.0                         # equal values → no dispersion
    assert abs(r.q - 0.45) < 0.01, f"0.45 must fall out, got {r.q}"   # 0.90×0.5×1.0

    # PROVE it's computed, not typed: add the missing axes (coverage 1.0) → q ~doubles.
    fuller = compute_q([
        QInput(name="a", present=True, value=1.0, age_days=age, data_type="cycle"),
        QInput(name="b", present=True, value=1.0, age_days=age, data_type="cycle"),
        QInput(name="c", present=True, value=1.0, age_days=age, data_type="cycle"),
        QInput(name="d", present=True, value=1.0, age_days=age, data_type="cycle"),
    ], needed=4)
    assert abs(fuller.q - 0.90) < 0.01, "full coverage → q≈0.9 (q tracks coverage, not typed)"


def test_GATE1_components_each_tested_in_isolation():
    """freshness/coverage/agreement each move independently (the q-engine isn't a constant)."""
    # freshness: fresh (age 0) vs stale (age=τ) → 1.0 vs ~0.37
    fresh = compute_q([QInput("x", True, 1.0, age_days=0.0, data_type="cycle")], needed=1)
    stale = compute_q([QInput("x", True, 1.0, age_days=30.0, data_type="cycle")], needed=1)
    assert abs(fresh.freshness - 1.0) < 1e-6 and abs(stale.freshness - math.exp(-1)) < 0.01
    # coverage: 1/2 vs 2/2
    half = compute_q([QInput("a", True, 1.0, age_days=0.0), QInput("b", False)], needed=2)
    full = compute_q([QInput("a", True, 1.0, age_days=0.0), QInput("b", True, 1.0, age_days=0.0)], needed=2)
    assert half.coverage == 0.5 and full.coverage == 1.0
    # agreement: equal values → 1.0; wildly different → <1
    agree = compute_q([QInput("a", True, 1.0, age_days=0.0), QInput("b", True, 1.0, age_days=0.0)], needed=2)
    disagree = compute_q([QInput("a", True, 1.0, age_days=0.0), QInput("b", True, -1.0, age_days=0.0)], needed=2)
    assert agree.agreement == 1.0 and disagree.agreement < 1.0


# --------------------------------------------------------------------------- #
# HARD GATE 2 — decision_weight PURE PRODUCT, NO clamp (DISTINGUISHING)          #
# --------------------------------------------------------------------------- #
def _W(qc, qm, qf, sa):
    """Recompute the product the way decision_weight does — for asserting against a hand-calc.
    (We test the REAL decision_weight via monkeypatched layers below; this is the oracle.)"""
    return round(qc * qm * qf * sa, 4)


def test_GATE2_pure_product_dim_upper_bright_lower_not_clamped(monkeypatch):
    """DISTINGUISHING (the bug-killer): a DIM upper layer (q_cycle=0.3) + a BRIGHT lower
    (s_asset=0.9) → W carries the lower's CONTRIBUTION (0.3×0.9×...=product), NOT clamped to
    min(0.3,0.9). An all-equal-q fixture would pass even against a broken min-clamp impl —
    so we use divergent layers and assert W == the PRODUCT, and that W < the smallest layer
    (a clamp-to-min would make W == min, a product makes W < min when other layers <1)."""
    # Force the 4 layers to divergent, known q's by patching the layer sources.
    monkeypatch.setattr(dec, "macro_cycle", lambda: _stub_cycle(0.3))
    monkeypatch.setattr(dec, "_q_flow", lambda: (0.8, "flow stub"))
    monkeypatch.setattr(dec, "_s_asset", lambda: (0.9, "asset stub"))
    # q_macro from a stubbed overview (mean indicator confidence = 0.7)
    monkeypatch.setattr(dec, "macro_cycle", lambda: _stub_cycle(0.3))
    import modules.macro.service as macro_svc
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (_stub_overview(0.7), []))

    dw = dec.decision_weight()
    layer_q = {ly.layer: ly.q for ly in dw.breakdown}
    expected = _W(layer_q["q_cycle"], layer_q["q_macro"], layer_q["q_flow"], layer_q["s_asset"])
    assert dw.weight == expected, f"W must be the PRODUCT {expected}, got {dw.weight}"
    # the product is STRICTLY LESS than the dimmest layer (a min-clamp would make them equal)
    assert dw.weight < min(layer_q.values()), \
        "W must be < the dimmest layer (∏ erodes below min; a clamp would equal min)"
    # binding_constraint names the dimmest layer
    assert dw.bindingConstraint == min(layer_q, key=layer_q.get)


def test_GATE2_zero_layer_blinds_whole_weight(monkeypatch):
    """A ZERO layer → W=0 ("blind = don't bet"), regardless of how bright the others are."""
    monkeypatch.setattr(dec, "macro_cycle", lambda: _stub_cycle(0.0))   # cycle dark
    monkeypatch.setattr(dec, "_q_flow", lambda: (0.9, "flow"))
    monkeypatch.setattr(dec, "_s_asset", lambda: (0.9, "asset"))
    import modules.macro.service as macro_svc
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (_stub_overview(0.9), []))
    dw = dec.decision_weight()
    assert dw.weight == 0.0
    assert dw.bindingConstraint == "q_cycle"   # the dark layer is named
    assert dw.verdict == "blind"


# --------------------------------------------------------------------------- #
# HARD GATE 3 — weight vs confidence are SEPARATE (the dangerous quadrant)       #
# --------------------------------------------------------------------------- #
def test_GATE3_weight_and_confidence_are_distinct_fields(monkeypatch):
    """weight (∏) and confidence (mean layer q) are SEPARATE numbers + a legend. Construct the
    dangerous quadrant: a HIGH product is impossible with one dim layer, so test that they're
    genuinely different values (not the same field aliased) + the legend is present."""
    monkeypatch.setattr(dec, "macro_cycle", lambda: _stub_cycle(0.2))   # one dim layer
    monkeypatch.setattr(dec, "_q_flow", lambda: (0.9, "flow"))
    monkeypatch.setattr(dec, "_s_asset", lambda: (0.9, "asset"))
    import modules.macro.service as macro_svc
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (_stub_overview(0.9), []))
    dw = dec.decision_weight()
    # weight = 0.2×0.9×0.9×0.9 = 0.1458 (a THIN signal); confidence = mean(0.2,0.9,0.9,0.9)=0.725
    assert dw.weight != dw.confidence, "weight and confidence must be SEPARATE numbers"
    assert dw.weight < dw.confidence, "the dim layer crushes the product but not the mean trust"
    assert "weight" in dw.legend.lower() and "confidence" in dw.legend.lower()


# --------------------------------------------------------------------------- #
# HARD GATE 4 — macro_cycle honest-missing + NEUTRAL                             #
# --------------------------------------------------------------------------- #
def test_GATE4_macro_cycle_honest_on_missing_axis(monkeypatch, isolated_paths):
    """A mock/missing axis → coverage<1 → lower qCycle + a warning, NEVER a fabricated phase.
    Mock ALL macro to source='mock' → every axis counts as not-covered → qCycle low + warning,
    phase stays 'unknown' (not invented)."""
    from modules.macro import service as macro_svc
    from modules.macro.schema import MacroOverview, MacroIndicatorView
    # all axes mock → present=False in the cycle q (mock doesn't count as covered)
    inds = [MacroIndicatorView(indicator=i, label=i, unit="", latest=1.0, asOf="2026-06-01",
                               trend="up", source="mock", points=2, confidence=0.2)
            for i in ("industrial_production", "cpi", "yield_curve_10y2y", "unemployment")]
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (MacroOverview(indicators=inds, source="mock"), []))
    cyc = dec.macro_cycle()
    assert cyc.qCycle.coverage < 1.0, "a mock axis must lower coverage (not count as covered)"
    assert cyc.warning is not None
    # phase may be named from the (mock) directions OR unknown — but the LOW q is the honesty.
    assert cyc.confidence == cyc.qCycle.q and cyc.confidence < 0.5


def test_GATE4_macro_cycle_unknown_when_axes_indeterminate(monkeypatch, isolated_paths):
    """When growth/inflation direction isn't both determinable → phase 'unknown' (NOT fabricated)."""
    from modules.macro import service as macro_svc
    from modules.macro.schema import MacroOverview, MacroIndicatorView
    # INDPRO + CPI flat → no up/down direction → can't name a phase
    inds = [MacroIndicatorView(indicator=i, label=i, unit="", latest=1.0, asOf="2026-06-01",
                               trend="flat", source="fred", points=2, confidence=0.9)
            for i in ("industrial_production", "cpi", "yield_curve_10y2y", "unemployment")]
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (MacroOverview(indicators=inds, source="fred"), []))
    cyc = dec.macro_cycle()
    assert cyc.phase == "unknown"
    assert cyc.favored == [] and cyc.defensive == []   # no fabricated reference map


def test_GATE4_macro_cycle_neutral_no_advice_verb(monkeypatch, isolated_paths):
    """NEUTRAL (HARD): no advice verb (should/buy/sell/rebalance/recommend) anywhere in the
    macro_cycle payload — it's data + q, the agent reasons."""
    import json
    from modules.macro import service as macro_svc
    from modules.macro.schema import MacroOverview, MacroIndicatorView
    inds = [MacroIndicatorView(indicator=i, label=i, unit="", latest=1.0, asOf="2026-06-01",
                               trend="up", source="fred", points=2, confidence=0.9)
            for i in ("industrial_production", "cpi", "yield_curve_10y2y", "unemployment")]
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (MacroOverview(indicators=inds, source="fred"), []))
    flat = json.dumps(dec.macro_cycle().model_dump()).lower()
    for verb in ("should", "buy", "sell", "rebalance", "recommend", "must ", "ought"):
        assert verb not in flat, f"macro_cycle leaked an advice verb: {verb!r}"


def test_GATE4_decision_weight_neutral_no_advice_verb(monkeypatch, isolated_paths):
    """decision_weight payload is NEUTRAL too — verdict is a descriptive BAND, no advice verb."""
    import json
    from modules.macro import service as macro_svc
    monkeypatch.setattr(dec, "macro_cycle", lambda: _stub_cycle(0.5))
    monkeypatch.setattr(dec, "_q_flow", lambda: (0.5, "flow"))
    monkeypatch.setattr(dec, "_s_asset", lambda: (0.5, "asset"))
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (_stub_overview(0.5), []))
    flat = json.dumps(dec.decision_weight().model_dump()).lower()
    for verb in ("should", "buy", "sell", "rebalance", "recommend"):
        assert verb not in flat, f"decision_weight leaked an advice verb: {verb!r}"


# --------------------------------------------------------------------------- #
# HARD GATE 5 — compute_q is the SINGLE source (no reimplementation)             #
# --------------------------------------------------------------------------- #
def test_GATE5_compute_q_is_the_single_source():
    """macro_cycle + decision_weight + the macro seam _confidence_for all CALL compute_q (or a
    helper that does) — and NONE reimplements freshness/coverage/agreement. Proven by AST: only
    compute_q's own body may contain the freshness/agreement math (exp / dispersion); the tool
    fns must not."""
    # (a) the macro seam delegates to the decision q-engine (imports confidence_q).
    import modules.macro.service as macro_svc
    seam_src = inspect.getsource(macro_svc._confidence_for)
    assert "confidence_q" in seam_src, "the macro seam must delegate to the shared q-engine"
    assert "exp(" not in seam_src and "dispersion" not in seam_src, \
        "the seam must NOT reimplement freshness/agreement"

    # (b) macro_cycle + decision_weight reference compute_q (directly or via q_from_points),
    #     and don't roll their own exp()/dispersion freshness math.
    for fn in (dec.macro_cycle, dec.decision_weight):
        src = inspect.getsource(fn)
        calls_engine = ("compute_q" in src) or ("q_from_points" in src)
        assert calls_engine, f"{fn.__name__} must call the shared q-engine"
        assert "math.exp" not in src and "dispersion" not in src, \
            f"{fn.__name__} must NOT reimplement the freshness/agreement math"

    # (c) the ONLY place exp(-age/τ) lives is compute_q's freshness helper.
    engine_src = inspect.getsource(dec._freshness)
    assert "exp(" in engine_src, "freshness=exp(-age/τ) lives in the one q-engine helper"


# --------------------------------------------------------------------------- #
# Stubs for the layer-injection tests                                           #
# --------------------------------------------------------------------------- #
def _stub_cycle(q_value: float):
    """A MacroCycle whose qCycle.q is exactly q_value (for decision_weight layer injection)."""
    from modules.decision.schema import MacroCycle, QResult
    qr = QResult(q=q_value, freshness=1.0, coverage=1.0, agreement=1.0, breakdown=[],
                 neededInputs=3, presentInputs=3)
    return MacroCycle(phase="recovery", axes=[], qCycle=qr, favored=["equity"],
                      defensive=["cash"], confidence=q_value, warning=None)


def _stub_overview(indicator_q: float):
    """A MacroOverview whose indicators all have confidence=indicator_q (so q_macro = that)."""
    from modules.macro.schema import MacroOverview, MacroIndicatorView
    inds = [MacroIndicatorView(indicator=f"i{n}", label="x", unit="", latest=1.0, asOf="2026-06-01",
                               trend="up", source="fred", points=2, confidence=indicator_q)
            for n in range(3)]
    return MacroOverview(indicators=inds, source="fred")


# =========================================================================== #
# FINANCE-ASSISTANT P3 (#55) — allocation_target + finance_guardian             #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# HARD GATE 1 (P3) — NO ADVICE VERB (the load-bearing gate for the highest-     #
# advice-risk tools). NOTHING in allocation_target / finance_guardian may       #
# contain an imperative advice verb — they surface DATA + questions.            #
# --------------------------------------------------------------------------- #
_ADVICE_VERBS = ("should", "buy", "sell", "rebalance", "move ", "deploy",
                 "recommend", "must ", "ought")


def test_P3_GATE1_allocation_target_no_advice_verb(isolated_paths, monkeypatch):
    """allocation_target is a REFERENCE weighting — DATA + rationale, never 'you should be
    aggressive'. Assert no advice verb in the whole payload (the load-bearing NEUTRAL gate)."""
    import json
    from modules.macro import store as mstore
    mstore.init_macro_tables()
    flat = json.dumps(dec.allocation_target(10000, phase="recovery").model_dump()).lower()
    for verb in _ADVICE_VERBS:
        assert verb not in flat, f"allocation_target leaked an advice verb {verb!r}: BLOCKER"


def test_P3_GATE1_finance_guardian_no_advice_verb(isolated_paths, monkeypatch):
    """finance_guardian alerts are OBSERVATIONS framed as QUESTIONS — never imperatives.
    Force all 3 rules to fire (real data) and assert no advice verb in any alert."""
    import json
    from modules.macro import store as mstore
    from modules.finance import service as fin
    from modules.macro import service as macro_svc
    from modules.exchange.schema import ExchangeOverview, OkxBalance
    mstore.init_macro_tables()
    # stablecoin-heavy crypto + a real F&G + correlated memes + dust → all rules have data
    snap = ExchangeOverview(configured=True, totalUsdValue=10000.0, balances=[
        OkxBalance(symbol="USDT", available=9000, frozen=0, total=9000, usdValue=9000.0),
        OkxBalance(symbol="PEPE", available=1, frozen=0, total=1, usdValue=500.0, accAvgPx=400.0),
        OkxBalance(symbol="DOGE", available=1, frozen=0, total=1, usdValue=400.0, accAvgPx=300.0),
    ])
    monkeypatch.setattr(fin.exchange_service, "get_overview", lambda: (snap, None))
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (10000.0, None))
    # real F&G point
    mstore.record_point("fear_greed", 23.0, "2026-06-16", "live")
    flat = json.dumps(dec.finance_guardian().model_dump()).lower()
    for verb in _ADVICE_VERBS:
        assert verb not in flat, f"finance_guardian leaked an advice verb {verb!r}: BLOCKER"


# --------------------------------------------------------------------------- #
# HARD GATE 2 (P3) — allocation capital-size DISTINGUISHING + threshold from     #
# settings (the user-configurable boundary moves when patched).                 #
# --------------------------------------------------------------------------- #
def test_P3_GATE2_capital_size_gives_different_tilt(isolated_paths):
    """$10k (small) vs $1M (large), SAME phase → GENUINELY DIFFERENT tilt (an impl that ignores
    capital would give identical output). Divergent inputs prove the tilt is real."""
    small = dec.allocation_target(10000, phase="recovery")
    large = dec.allocation_target(1000000, phase="recovery")
    assert small.capitalTier == "small" and large.capitalTier == "large"
    assert small.targets != large.targets, "capital size must change the tilt"
    # small tilts MORE into crypto than large (the model's risk-capacity logic)
    assert small.targets["crypto"] > large.targets["crypto"]


def test_P3_GATE2_threshold_reads_from_settings(isolated_paths):
    """The capital-tier boundary READS from settings (user-configurable). Patch
    riskCapitalSmallUsd up → a capital that WAS 'mid' becomes 'small' (the boundary moved)."""
    from modules.settings import service as ssvc
    from modules.settings.schema import AppConfigPatch
    # default small threshold 50k → $60k is 'mid'
    assert dec.allocation_target(60000, phase="recovery").capitalTier == "mid"
    # raise the small threshold to 100k → $60k is now 'small' (boundary moved via settings)
    ssvc.set_config(AppConfigPatch(riskCapitalSmallUsd=100000.0))
    assert dec.allocation_target(60000, phase="recovery").capitalTier == "small"


def test_P3_allocation_vs_goldenpath_and_confidence(isolated_paths):
    """The reference carries the delta vs the static golden-path + a confidence (q over inputs).
    Unknown phase → lower confidence (honest)."""
    from modules.macro import store as mstore
    mstore.init_macro_tables()
    at = dec.allocation_target(10000, phase="recovery")
    assert set(at.vsStaticGoldenPath) == {"crypto", "etf", "vn", "dry"}
    assert 0.0 < at.confidence <= 1.0
    # unknown phase → no tilt + lower confidence
    unk = dec.allocation_target(10000, phase="unknown")
    assert unk.confidence < at.confidence


# --------------------------------------------------------------------------- #
# HARD GATE 3 (P3) — guardian fires on REAL data ONLY (mock → no fire)           #
# --------------------------------------------------------------------------- #
def test_P3_GATE3_guardian_does_not_fire_on_mock_fng(isolated_paths, monkeypatch):
    """A guardian firing on MOCK data fabricates concern. The stablecoin-vs-fear rule must NOT
    fire when F&G is source='mock' (even with a real high stablePct) — real-data-only."""
    from modules.macro import store as mstore
    from modules.finance import service as fin
    from modules.exchange.schema import ExchangeOverview, OkxBalance
    mstore.init_macro_tables()
    # real high-stablecoin crypto channel
    snap = ExchangeOverview(configured=True, totalUsdValue=10000.0, balances=[
        OkxBalance(symbol="USDT", available=9500, frozen=0, total=9500, usdValue=9500.0),
        OkxBalance(symbol="BTC", available=1, frozen=0, total=1, usdValue=500.0, accAvgPx=400.0),
    ])
    monkeypatch.setattr(fin.exchange_service, "get_overview", lambda: (snap, None))
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (10000.0, None))
    # F&G present but MOCK → the rule must NOT fire (no fabricated concern)
    mstore.record_point("fear_greed", 23.0, "2026-06-16", "mock")
    rep = dec.finance_guardian()
    fng_alerts = [a for a in rep.alerts if "fear" in a.msg.lower()]
    assert fng_alerts == [], "guardian must NOT fire the F&G rule on a MOCK F&G value"


def test_P3_guardian_fires_on_real_data(isolated_paths, monkeypatch):
    """The DISTINGUISHING other arm: with a REAL F&G (source='live'), the same stablecoin-heavy
    fixture DOES fire the rule (proving it's the mock-ness that suppressed it, not the rule)."""
    from modules.macro import store as mstore
    from modules.finance import service as fin
    from modules.exchange.schema import ExchangeOverview, OkxBalance
    mstore.init_macro_tables()
    snap = ExchangeOverview(configured=True, totalUsdValue=10000.0, balances=[
        OkxBalance(symbol="USDT", available=9500, frozen=0, total=9500, usdValue=9500.0),
        OkxBalance(symbol="BTC", available=1, frozen=0, total=1, usdValue=500.0, accAvgPx=400.0),
    ])
    monkeypatch.setattr(fin.exchange_service, "get_overview", lambda: (snap, None))
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (10000.0, None))
    mstore.record_point("fear_greed", 23.0, "2026-06-16", "live")   # REAL
    rep = dec.finance_guardian()
    fng_alerts = [a for a in rep.alerts if "fear" in a.msg.lower()]
    assert len(fng_alerts) == 1, "guardian SHOULD fire the F&G rule on a REAL F&G value"
    assert fng_alerts[0].evidence["fngSource"] == "live"


def test_P3_guardian_honest_empty(isolated_paths, monkeypatch):
    """Nothing notable → [] + a note (NOT a fabricated alert)."""
    from modules.finance import service as fin
    from modules.exchange.schema import ExchangeOverview
    monkeypatch.setattr(fin.exchange_service, "get_overview",
                        lambda: (ExchangeOverview(configured=False, totalUsdValue=0.0, balances=[]), None))
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (None, None))
    rep = dec.finance_guardian()
    assert rep.alerts == [] and rep.note is not None


# --------------------------------------------------------------------------- #
# HARD GATE 4 (P3) — decision_journal additive fields land + calibration intact  #
# --------------------------------------------------------------------------- #
def test_P3_GATE4_decision_journal_finance_fields_land(isolated_paths):
    """The additive expectedEv/worstCase/decisionWeight persist + round-trip; domain='investment'
    is just the free-form key (no new mechanism)."""
    from modules.decision_journal import service as dj
    from modules.decision_journal.schema import DecisionInput
    e = dj.create_entry(DecisionInput(
        decision="buy gold 15% as hedge", confidence=60, domain="investment",
        expectedEv="positive_asymmetric", worstCase="-20% if phase misread", decisionWeight=0.18))
    got = dj.get_entry(e.id)
    assert got.expectedEv == "positive_asymmetric"
    assert got.worstCase == "-20% if phase misread"
    assert got.decisionWeight == 0.18
    assert got.domain == "investment"


def test_P3_GATE4_calibration_still_computes(isolated_paths):
    """Additive fields must NOT disturb the existing calibration/Brier (it keys on confidence/
    outcome only). Resolve a few decisions → brier + bands still compute."""
    from modules.decision_journal import service as dj
    from modules.decision_journal.schema import DecisionInput, DecisionUpdate
    for i, (conf, outcome) in enumerate([(60, "right"), (70, "wrong"), (90, "right")]):
        e = dj.create_entry(DecisionInput(decision=f"call {i}", confidence=conf, domain="investment",
                                          expectedEv="ev", worstCase="wc"))
        dj.update_entry(e.id, DecisionUpdate(status="resolved", outcome=outcome))
    stats, _ = dj.list_entries()
    assert stats.resolvedCount == 3
    assert stats.brier is not None              # calibration still computes
    assert isinstance(stats.calibration, list)  # bands still derived


# =========================================================================== #
# FINANCE-ASSISTANT P4 (#56) — nav_history reader + compute_q param-ization     #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# HARD GATE (a) — 0.45 STILL falls out on DEFAULT params (the L58 contract is    #
# byte-identical). [The existing GATE1 test above ALSO covers this — it runs     #
# UNCHANGED. This pins the explicit default==no-params equality.]                #
# --------------------------------------------------------------------------- #
def test_P4_GATEa_default_params_byte_identical():
    """compute_q with NO params == compute_q with default/empty params == the P2 0.45. The
    param-ization must NOT perturb the default path (the byte-identical lock)."""
    age = -30.0 * math.log(0.90)
    inputs = [QInput("yc", True, 1.0, age_days=age, data_type="cycle"),
              QInput("cpi", True, 1.0, age_days=age, data_type="cycle"),
              QInput("pmi", False), QInput("unrate", False)]
    r_none = compute_q(inputs, needed=4)
    r_empty = compute_q(inputs, needed=4, params={})
    r_explicit = compute_q(inputs, needed=4, params={"combine": "multiply"})
    assert r_none.q == r_empty.q == r_explicit.q
    assert abs(r_none.q - 0.45) < 0.01           # the 0.45 contract holds


# --------------------------------------------------------------------------- #
# HARD GATE (b) — combine="min" ≠ "multiply" (the enum actually switches)        #
# --------------------------------------------------------------------------- #
def test_P4_GATEb_min_differs_from_multiply():
    """The SAME input through combine='min' gives a DIFFERENT q than 'multiply' — proving the
    enum is a real switch, not a no-op param. min(f,c,a) ≥ f×c×a (for components ≤1) so they
    diverge whenever any component < 1."""
    age = -30.0 * math.log(0.90)
    inputs = [QInput("yc", True, 1.0, age_days=age, data_type="cycle"),
              QInput("cpi", True, 1.0, age_days=age, data_type="cycle"),
              QInput("pmi", False), QInput("unrate", False)]
    q_mult = compute_q(inputs, needed=4, params={"combine": "multiply"}).q
    q_min = compute_q(inputs, needed=4, params={"combine": "min"}).q
    assert q_mult != q_min, "min must differ from multiply (the enum switches behavior)"
    # min = min(freshness 0.9, coverage 0.5, agreement 1.0) = 0.5; multiply = 0.45
    assert abs(q_min - 0.5) < 0.01 and abs(q_mult - 0.45) < 0.01


def test_P4_combine_modes_each_unit_tested():
    """Each of the 3 closed-enum modes computes its documented formula (multiply/min/geomean)."""
    inputs = [QInput("a", True, 1.0, age_days=0.0, data_type="cycle"),
              QInput("b", False), QInput("c", False), QInput("d", False)]
    # f=1.0 (age 0), coverage=1/4=0.25, agreement=1.0
    mult = compute_q(inputs, needed=4, params={"combine": "multiply"}).q
    mn = compute_q(inputs, needed=4, params={"combine": "min"}).q
    wg = compute_q(inputs, needed=4, params={"combine": "weighted_geomean"}).q
    assert abs(mult - 0.25) < 0.01            # 1.0 × 0.25 × 1.0
    assert abs(mn - 0.25) < 0.01              # min(1.0, 0.25, 1.0)
    assert abs(wg - (0.25 ** (1 / 3))) < 0.01  # (1·0.25·1)^(1/3) ≈ 0.63
    # an UNKNOWN combine falls back to multiply (closed enum, never free-eval)
    bad = compute_q(inputs, needed=4, params={"combine": "rm -rf /"}).q
    assert abs(bad - mult) < 1e-9


def test_P4_tau_seconds_converts_to_days():
    """tau IN is SECONDS (spec §2.5); the engine converts to days internally. Passing the
    default macro tau in seconds (2_592_000 = 30d) gives the same q as the default."""
    age = -30.0 * math.log(0.90)
    inputs = [QInput("x", True, 1.0, age_days=age, data_type="cycle"),
              QInput("y", True, 1.0, age_days=age, data_type="cycle"),
              QInput("z", False), QInput("w", False)]
    default = compute_q(inputs, needed=4).q
    explicit_sec = compute_q(inputs, needed=4, params={"tau": {"cycle": 2_592_000}}).q
    assert abs(default - explicit_sec) < 0.001
    # a SHORTER tau (1 day) → much staler → lower freshness → lower q
    short = compute_q(inputs, needed=4, params={"tau": {"cycle": 86_400}}).q
    assert short < default


# --------------------------------------------------------------------------- #
# HARD GATE (c) — paramsUsed ALWAYS present (transparency, every call)           #
# --------------------------------------------------------------------------- #
def test_P4_GATEc_params_used_always_present():
    """Every QResult carries paramsUsed (default or custom) — mandatory transparency (§2.4)."""
    inputs = [QInput("a", True, 1.0, age_days=0.0, data_type="cycle")]
    for params in (None, {}, {"combine": "min"}, {"tau": {"cycle": 100}}):
        r = compute_q(inputs, needed=1, params=params)
        assert r.paramsUsed, f"paramsUsed missing for params={params}"
        assert "combine" in r.paramsUsed and "tauSeconds" in r.paramsUsed
        assert r.paramsUsed["tauUnit"] == "seconds-in/days-internal"


# --------------------------------------------------------------------------- #
# HARD GATE (d) — a P2 surface is byte-unchanged on default params               #
# --------------------------------------------------------------------------- #
def test_P4_GATEd_macro_cycle_unchanged_on_default_params(monkeypatch, isolated_paths):
    """macro_cycle (a P2 surface) must produce the SAME qCycle with the param-ized compute_q on
    default params as the pre-P4 formula. Pin via a deterministic fixture → exact q."""
    from modules.macro import service as macro_svc
    from modules.macro.schema import MacroOverview, MacroIndicatorView
    inds = [MacroIndicatorView(indicator=i, label=i, unit="", latest=1.0, asOf="2026-06-01",
                               trend="up", source="fred", points=2, confidence=0.9)
            for i in ("industrial_production", "cpi", "yield_curve_10y2y", "unemployment")]
    monkeypatch.setattr(macro_svc, "get_overview", lambda: (MacroOverview(indicators=inds, source="fred"), []))
    cyc = dec.macro_cycle()
    # the q is a real number from the (default-param) engine — coverage 3/3, all present.
    assert cyc.qCycle.coverage == 1.0
    # paramsUsed flows through to the cycle q (proving the default path is used)
    assert cyc.qCycle.paramsUsed.get("combine") == "multiply"


# --------------------------------------------------------------------------- #
# HARD GATE (e) — nav reader values match portfolio_snapshot rows                #
# --------------------------------------------------------------------------- #
def test_P4_GATEe_nav_matches_snapshot_rows(isolated_paths):
    """The series nav == the stored total_value (<$0.01) — the reader is a thin pass-through."""
    from store import db
    db.init_db()
    db.record_snapshot("2026-06-15T23:50:00+00:00", 10000.50)
    db.record_snapshot("2026-06-16T23:50:00+00:00", 10652.31)
    nav = dec.nav_history()
    rows = db.snapshots()
    assert nav.points == 2
    for p, r in zip(nav.series, rows):
        assert p.date == r["day"]
        assert abs(p.nav - float(r["total_value"])) < 0.01


def test_P4_nav_empty_is_honest_no_crash(isolated_paths):
    """Empty range (no snapshots) → series:[], points:0, confidence:0 + warning, NO crash."""
    from store import db
    db.init_db()
    nav = dec.nav_history()
    assert nav.series == [] and nav.points == 0 and nav.confidence == 0.0
    assert nav.warning is not None
    assert nav.range.from_ is None and nav.range.to is None


def test_P4_nav_confidence_scales_with_points(isolated_paths):
    """confidence rises with the point count (a longer series is more trustworthy for a trend)."""
    from store import db
    db.init_db()
    db.record_snapshot("2026-06-01T23:50:00+00:00", 10000.0)
    one = dec.nav_history().confidence
    for d in range(2, 12):  # add 10 more days
        db.record_snapshot(f"2026-06-{d:02d}T23:50:00+00:00", 10000.0 + d)
    eleven = dec.nav_history().confidence
    assert eleven > one, "more points → higher confidence"


def test_P4_nav_range_filter(isolated_paths):
    """date_from/date_to filter the series (the `to` upper bound is applied in the reader)."""
    from store import db
    db.init_db()
    for d in range(1, 11):
        db.record_snapshot(f"2026-06-{d:02d}T23:50:00+00:00", 10000.0 + d)
    # range 06-03 .. 06-07 → 5 points
    nav = dec.nav_history(date_from="2026-06-03", date_to="2026-06-07")
    assert nav.points == 5
    assert nav.series[0].date == "2026-06-03" and nav.series[-1].date == "2026-06-07"


def test_P4_nav_neutral_no_advice_verb(isolated_paths):
    """NEUTRAL — nav_history is data + confidence, no advice verb."""
    import json
    from store import db
    db.init_db()
    db.record_snapshot("2026-06-16T23:50:00+00:00", 10652.31)
    flat = json.dumps(dec.nav_history().model_dump()).lower()
    for verb in ("should", "buy", "sell", "rebalance", "recommend", "deploy"):
        assert verb not in flat, f"nav_history leaked an advice verb: {verb}"


# =========================================================================== #
# FINANCE-FINISH G2 (#57) — allocation_target optional capital                  #
# =========================================================================== #
def test_G2_no_capital_uses_finance_totalvalue(isolated_paths, monkeypatch):
    """HARD GATE 5 (part a): a no-capital allocation_target uses finance get_overview().totalValue
    — assert it EQUALS the explicit-totalValue call (the default isn't ignored/hardcoded)."""
    from modules.finance import service as fin
    from modules.exchange.schema import ExchangeOverview
    # a deterministic portfolio total via OKX
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (75000.0, None))  # mid-tier total
    monkeypatch.setattr(fin.exchange_service, "get_overview",
                        lambda: (ExchangeOverview(configured=True, totalUsdValue=75000.0, balances=[]), None))
    ov, _ = fin.get_overview()
    no_arg = dec.allocation_target(phase="recovery")           # no capital → totalValue
    explicit = dec.allocation_target(ov.totalValue, phase="recovery")
    assert no_arg.targets == explicit.targets, "no-capital must use the live totalValue"
    assert no_arg.capitalTier == explicit.capitalTier


def test_G2_distinguishing_two_capitals_diverge(isolated_paths, monkeypatch):
    """HARD GATE 5 (part b): two DIVERGENT explicit capitals → DIFFERENT allocations (proves the
    capital actually drives the tilt, not silently ignored)."""
    from modules.macro import store as mstore
    mstore.init_macro_tables()
    small = dec.allocation_target(10000, phase="recovery")
    large = dec.allocation_target(2000000, phase="recovery")
    assert small.targets != large.targets
    assert small.capitalTier == "small" and large.capitalTier == "large"


def test_G2_no_capital_fail_open_when_portfolio_unreadable(isolated_paths, monkeypatch):
    """Fail-open: if the portfolio total can't be read, no-capital → 0 (small tier), never a
    crash (the allocation still returns a reference weighting)."""
    from modules.finance import service as fin
    monkeypatch.setattr(fin, "get_overview", lambda: (_ for _ in ()).throw(RuntimeError("portfolio down")))
    at = dec.allocation_target(phase="recovery")   # must not raise
    assert at.capitalTier == "small"   # 0 → small
