"use client";
/* ============================================================
   DEC — Decision Cockpit (FINANCE-ASSISTANT P1–P4). Folds the 4 tower tools + the
   NAV line into ONE screen. Reads /decision/{weight,macro-cycle,allocation,guardian,
   nav-history} via useDecision.

   NEUTRAL (load-bearing): the payloads are NEUTRAL by backend design — this screen
   renders DATA + the guardian's QUESTIONS, NEVER advice. NO advice imperatives in any
   label/copy (buy/sell/should/rebalance/move/deploy/recommend/must/ought). The verdict
   WORD + guardian msg QUESTIONS are rendered VERBATIM.

   HONEST CONFIDENCE (load-bearing, §116): `weight` (signal strength = ∏ layer-q) and
   `confidence` (trust in the measurement) are TWO DISTINCT numbers — rendered as two
   distinct visuals, never one conflated "score". A thin W (low weight / low confidence)
   reads as LOW CONVICTION at a glance — de-emphasized, NOT a bright green "go".

   SELF-DESCRIBING RAW: every q/W/delta is backend-computed — the FE renders + formats +
   colors, NEVER recomputes. A wrong number is a backend bug (report, don't patch).
   States: loading · error (only when ALL sections fail) · per-section degrade.
   ============================================================ */
import { useDecision, confidenceBand, layerLabel, deltaText } from "@/lib/useDecision";
import { LoadErrorShell } from "@/components/LoadErrorShell";
import { buildScale, linePoints, areaPath, xAt, yAt } from "@/lib/chart-geometry";
import { fmtUSD, fmtPct, relativeTime } from "@/lib/format";
import { apiBase } from "@/lib/api";
import type { GuardianAlert, AllocTargets } from "@/lib/types";

const CHANNEL_LABEL: Record<string, string> = {
  crypto: "Crypto", etf: "ETF / Chứng khoán", vn: "Cổ phiếu VN", dry: "Dry powder",
};
const CHANNEL_COLOR: Record<string, string> = {
  crypto: "var(--accent)", etf: "#4DA6FF", vn: "#a877ff", dry: "#4a3a2a",
};
const NAV_W = 720;
const NAV_H = 150;

/** "YYYY-MM-DD" → "DD/MM". */
function dayLabel(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  return m ? `${m[3]}/${m[2]}` : day;
}

/** 0–1 → integer %, null-safe. */
function pct01(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

/** Per-section pending placeholder (#71 progressive render): a section whose data
 *  hasn't arrived yet shows this skeleton INSIDE its own panel, so the fast sections
 *  paint immediately while a slow one (e.g. weight ~3s) fills in — no all-or-nothing
 *  blank-hang. */
function SectionPending({ testId }: { testId: string }) {
  return (
    <div className="hint faint" style={{ padding: "16px" }} data-testid={testId}>
      đang tải…
    </div>
  );
}

export default function DecisionPage() {
  const { weight, macroCycle, allocation, guardian, navHistory, status, reload } = useDecision();

  // #71: do NOT gate the whole page on a single "loading" — the hook fetches the 5
  // sections in parallel and exposes each independently, so we render the shell +
  // every panel immediately and let each section show its own pending/data/error
  // state. (A 10s blank used to hang the page waiting for the slowest endpoint.)

  // hard error only when EVERY section failed (backend down).
  // #138-P1a-rollout — the error branch is the shared <LoadErrorShell> (error-only here;
  // loading is per-section). Exact copy/testid/wrapper preserved verbatim.
  if (status === "error") {
    return (
      <LoadErrorShell
        status="error"
        sectionClassName="view"
        dataScreen="DEC"
        errorTestid="decision-error"
        errorLabel={<>Không tải được decision cockpit. Kiểm tra backend ({apiBase}).</>}
        reload={reload}
        loadingLabel={null}
      >
        {null}
      </LoadErrorShell>
    );
  }

  const w = weight.data;
  // honest-confidence: confidence band de-emphasizes a thin signal.
  const confBand = w ? confidenceBand(w.confidence) : null;
  // weight is on a 0–1 ∏-of-q scale; small numbers are the norm → show as % for legibility.
  const weightPct = w ? `${(w.weight * 100).toFixed(2)}%` : "—";

  return (
    <section className="view tight" data-screen="DEC" data-testid="decision-screen">
      <div className="vtitle">
        <h1>Decision Cockpit</h1>
        <span className="sub">tháp quyết định · dữ liệu trung lập (bạn quyết định)</span>
        <span className="sp" />
        <button className="btn sm" type="button" onClick={reload} data-testid="decision-reload">
          Tải lại
        </button>
      </div>

      {/* ─────────── W GAUGE — the honest-confidence centerpiece ─────────── */}
      <div className="panel" data-testid="decision-weight">
        <div className="phead">
          <span className="kicker">Decision Weight · W = ∏ q</span>
          {w && (
            <span className={`sbadge ${verdictToneCls(w.verdict)}`} data-testid="weight-verdict">
              {w.verdict}
            </span>
          )}
        </div>
        {weight.errMsg ? (
          <div className="hint neg" style={{ padding: "16px" }} data-testid="weight-degraded">
            ⚠ Lớp W lỗi: {weight.errMsg}
          </div>
        ) : w ? (
          <div style={{ padding: "16px 18px", display: "grid", gridTemplateColumns: "minmax(220px,300px) 1fr", gap: 20, alignItems: "start" }}>
            {/* TWO DISTINCT NUMBERS (§116): weight (signal strength) vs confidence (trust).
                Rendered as two separate stat blocks — never one conflated score. */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div
                className={`wgate ${confBand?.tone === "high" ? "ok" : confBand?.tone === "mid" ? "warn" : "blocked"}`}
                data-testid="weight-conviction"
                title="W thấp + tín hiệu mỏng = ít cơ sở để hành động (không phải đèn xanh)"
              >
                <div className="wgate-body">
                  <span className="kicker" style={{ marginBottom: 2 }}>Signal strength (W)</span>
                  <b className="num" style={{ fontSize: 30 }} data-testid="weight-value">{weightPct}</b>
                  <span className="mut" style={{ fontSize: 11 }}>
                    sức mạnh tín hiệu = tích các lớp q
                  </span>
                </div>
              </div>
              <div className="stat" data-testid="weight-confidence" style={{ gap: 3 }}>
                <span className="sl">Confidence · độ tin cậy</span>
                <span className="sv num">
                  {pct01(w.confidence)}{" "}
                  <span className={`sbadge ${confBand?.cls}`} style={{ fontSize: 9, verticalAlign: "middle" }} data-testid="confidence-band">
                    {confBand?.label}
                  </span>
                </span>
                <span className="sd faint">tin tưởng vào phép đo (khác với W)</span>
              </div>
            </div>

            {/* layer breakdown + the self-describing legend + math */}
            <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
              <div className="hint" style={{ lineHeight: 1.55, fontSize: 11 }} data-testid="weight-legend">
                {w.legend}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {w.breakdown.map((b) => {
                  const isBinding = b.layer === w.bindingConstraint;
                  return (
                    <div key={b.layer} data-testid={`layer-${b.layer}`}>
                      <div className="mrow" style={{ alignItems: "center", gap: 10, padding: "4px 0", borderBottom: 0 }}>
                        <span className="k" style={{ minWidth: 160 }}>
                          {layerLabel(b.layer)}
                          {isBinding && (
                            <span className="tagchip mid" style={{ marginLeft: 7, fontSize: 9 }} data-testid={`binding-${b.layer}`}>
                              ràng buộc · dimmest
                            </span>
                          )}
                        </span>
                        <span className="barc" style={{ flex: 1, width: "auto" }}>
                          <i style={{ width: `${Math.max(0, Math.min(100, b.q * 100))}%`, background: isBinding ? "var(--amber)" : "var(--accent)" }} />
                        </span>
                        <span className="num faint" style={{ width: 52, textAlign: "right" }}>{b.q.toFixed(3)}</span>
                      </div>
                      <div className="faint" style={{ fontSize: 10.5, paddingLeft: 2, lineHeight: 1.4, color: "var(--tx-1)" }} data-testid={`layer-note-${b.layer}`}>
                        {/* #148-R2: bump these small (10.5px) load-bearing explanatory lines
                            from .faint's --tx-2 (contrast 3.23 — fails WCAG AA) to --tx-1
                            (6.63 — passes) INLINE, so the q-layer reasoning is readable.
                            Inline-only: the shared .faint class rule is NOT modified. */}
                        {b.note}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="hint faint" style={{ fontSize: 10.5, lineHeight: 1.5, borderTop: "1px solid var(--line)", paddingTop: 8, color: "var(--tx-1)" }} data-testid="weight-explanation">
                {/* #148-R2: same contrast bump (--tx-1) for the W=∏q explanation line. */}
                {w.explanation}
              </div>
            </div>
          </div>
        ) : (
          <SectionPending testId="weight-pending" />
        )}
      </div>

      {/* ─────────── INVESTMENT CLOCK ─────────── */}
      <div className="panel" data-testid="decision-cycle">
        <div className="phead">
          <span className="kicker">Investment Clock · pha chu kỳ</span>
          {macroCycle.data && (
            <span className="sbadge sb-slow" data-testid="cycle-phase" style={{ textTransform: "none" }}>
              {macroCycle.data.phase}
            </span>
          )}
        </div>
        {macroCycle.errMsg ? (
          <div className="hint neg" style={{ padding: "16px" }} data-testid="cycle-degraded">⚠ Lớp chu kỳ lỗi: {macroCycle.errMsg}</div>
        ) : macroCycle.data ? (
          <div style={{ padding: "12px 16px 16px" }}>
            <div className="grid g-3" data-testid="cycle-axes">
              {macroCycle.data.axes.map((ax) => (
                <div key={ax.axis} className="card" style={{ padding: "12px 14px", gap: 4, opacity: ax.present ? 1 : 0.6 }} data-testid={`axis-${ax.axis}`}>
                  <span className="kicker">{ax.axis}</span>
                  <span className="num" style={{ fontSize: 15, fontWeight: 600 }}>
                    {ax.direction === "up" ? "▲" : ax.direction === "down" ? "▼" : "▬"} {ax.direction}
                  </span>
                  <span className="faint" style={{ fontSize: 10.5, lineHeight: 1.4, color: "var(--tx-1)" }}>{ax.detail}</span>
                  {!ax.present && <span className="tagchip" style={{ fontSize: 9, alignSelf: "flex-start" }} data-testid={`axis-missing-${ax.axis}`}>mock / thiếu dữ liệu</span>}
                </div>
              ))}
            </div>
            <div className="hint" style={{ marginTop: 10, fontSize: 11 }} data-testid="cycle-q">
              q chu kỳ = {macroCycle.data.qCycle.q.toFixed(3)} · freshness {macroCycle.data.qCycle.freshness.toFixed(2)} ·
              coverage {macroCycle.data.qCycle.coverage.toFixed(2)} ({macroCycle.data.qCycle.presentInputs}/{macroCycle.data.qCycle.neededInputs} chỉ số) ·
              agreement {macroCycle.data.qCycle.agreement.toFixed(2)}
            </div>
          </div>
        ) : (
          <SectionPending testId="cycle-pending" />
        )}
      </div>

      {/* ─────────── GUARDIAN — questions, NOT advice ─────────── */}
      <div className="panel" data-testid="decision-guardian">
        <div className="phead">
          <span className="kicker">Guardian · câu hỏi rủi ro</span>
          {guardian.data && (
            <span className="hint" style={{ marginLeft: "auto" }} data-testid="guardian-meta">
              {guardian.data.alerts.length} câu hỏi · cập nhật {relativeTime(guardian.data.asOf)}
            </span>
          )}
        </div>
        {guardian.errMsg ? (
          <div className="hint neg" style={{ padding: "16px" }} data-testid="guardian-degraded">⚠ Guardian lỗi: {guardian.errMsg}</div>
        ) : guardian.data ? (
          guardian.data.alerts.length === 0 ? (
            <div className="hint" style={{ padding: "18px 16px" }} data-testid="guardian-empty">
              Không có câu hỏi nào lúc này.
            </div>
          ) : (
            <div style={{ padding: "10px 14px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
              {guardian.data.alerts.map((al, i) => (
                <GuardianCard key={i} alert={al} idx={i} />
              ))}
            </div>
          )
        ) : (
          <SectionPending testId="guardian-pending" />
        )}
      </div>

      {/* ─────────── ALLOCATION — reference weighting (data, not instruction) ─────────── */}
      <div className="panel" data-testid="decision-allocation">
        <div className="phead">
          <span className="kicker">Allocation reference · trọng số tham chiếu</span>
          {allocation.data && (
            <span className="hint" style={{ marginLeft: "auto" }} data-testid="alloc-tier">
              pha {allocation.data.phase} · vốn {allocation.data.capitalTier}
            </span>
          )}
        </div>
        {allocation.errMsg ? (
          <div className="hint neg" style={{ padding: "16px" }} data-testid="alloc-degraded">⚠ Allocation lỗi: {allocation.errMsg}</div>
        ) : allocation.data ? (
          <div style={{ padding: "10px 16px 14px" }}>
            {(Object.keys(allocation.data.targets) as (keyof AllocTargets)[]).map((ch) => {
              const target = allocation.data!.targets[ch];
              const delta = deltaText(allocation.data!.vsStaticGoldenPath[ch]);
              const why = allocation.data!.rationale[ch];
              return (
                <div key={ch} style={{ padding: "7px 0", borderBottom: "1px solid color-mix(in oklch, var(--line) 55%, transparent)" }} data-testid={`alloc-${ch}`}>
                  <div className="mrow" style={{ alignItems: "center", gap: 10, borderBottom: 0, padding: 0 }}>
                    <span className="k" style={{ minWidth: 130, display: "inline-flex", alignItems: "center", gap: 7 }}>
                      <i style={{ width: 9, height: 9, borderRadius: 2, background: CHANNEL_COLOR[ch] ?? "var(--accent)" }} />
                      {CHANNEL_LABEL[ch] ?? ch}
                    </span>
                    <span className="barc" style={{ flex: 1, width: "auto" }}>
                      <i style={{ width: `${Math.max(0, Math.min(100, target))}%`, background: CHANNEL_COLOR[ch] ?? "var(--accent)" }} />
                    </span>
                    <span className="num" style={{ width: 52, textAlign: "right", fontWeight: 600 }}>{target.toFixed(0)}%</span>
                    <span className={`tagchip ${delta.cls}`} title="lệch so với golden-path tĩnh (pp)" data-testid={`alloc-delta-${ch}`} style={{ width: 64, textAlign: "center" }}>
                      {delta.text}
                    </span>
                  </div>
                  {why && <div className="faint" style={{ fontSize: 10.5, paddingLeft: 137, lineHeight: 1.4, marginTop: 2, color: "var(--tx-1)" }} data-testid={`alloc-why-${ch}`}>{why}</div>}
                </div>
              );
            })}
            {allocation.data.note && (
              <div className="hint" style={{ marginTop: 11, fontSize: 11, lineHeight: 1.5 }} data-testid="alloc-note">
                {allocation.data.note}
              </div>
            )}
          </div>
        ) : (
          <SectionPending testId="alloc-pending" />
        )}
      </div>

      {/* ─────────── NAV LINE — short-series honesty ─────────── */}
      <NavPanel
        data={navHistory.data}
        errMsg={navHistory.errMsg}
      />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  GuardianCard — renders a guardian alert. msg is a QUESTION,        */
/*  rendered VERBATIM (NEUTRAL). evidence numbers shown as chips.      */
/* ------------------------------------------------------------------ */
function GuardianCard({ alert, idx }: { alert: GuardianAlert; idx: number }) {
  const sevColor = alert.severity === "high" ? "var(--red)" : alert.severity === "low" ? "var(--tx-2)" : "var(--amber)";
  return (
    <div className="al" style={{ background: "var(--bg-0)", border: "1px solid var(--line)", alignItems: "flex-start" }} data-testid={`guardian-alert-${idx}`}>
      <span className="ad" style={{ background: sevColor, boxShadow: `0 0 8px ${sevColor}` }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="at" style={{ lineHeight: 1.5 }} data-testid={`guardian-msg-${idx}`}>{alert.msg}</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6, alignItems: "center" }}>
          <span className="sbadge" style={{ color: sevColor, background: "transparent", border: `1px solid ${sevColor}`, fontSize: 9 }}>
            {alert.severity}
          </span>
          {Object.entries(alert.evidence).map(([k, v]) => (
            <span key={k} className="tagchip" style={{ fontSize: 9.5 }} data-testid={`guardian-ev-${idx}-${k}`}>
              {k}: {formatEvidence(v)}
            </span>
          ))}
          {alert.sources.length > 0 && (
            <span className="faint" style={{ fontSize: 9.5 }} data-testid={`guardian-src-${idx}`}>
              nguồn: {alert.sources.join(", ")}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/** evidence value → compact display string (number rounded, others stringified). */
function formatEvidence(v: unknown): string {
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (v == null) return "—";
  return String(v);
}

/* ------------------------------------------------------------------ */
/*  NavPanel — the NAV line. SHORT-SERIES HONESTY: render the warning  */
/*  when short; do NOT draw a confident trend from few points.         */
/* ------------------------------------------------------------------ */
function NavPanel({ data, errMsg }: { data: import("@/lib/types").NavHistory | null; errMsg: string }) {
  if (errMsg) {
    return (
      <div className="panel" data-testid="decision-nav">
        <div className="phead"><span className="kicker">NAV · giá trị ròng theo ngày</span></div>
        <div className="hint neg" style={{ padding: "16px" }} data-testid="nav-degraded">⚠ NAV lỗi: {errMsg}</div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="panel" data-testid="decision-nav">
        <div className="phead"><span className="kicker">NAV · giá trị ròng theo ngày</span></div>
        <SectionPending testId="nav-pending" />
      </div>
    );
  }

  const values = data.series.map((p) => p.nav);
  const scale = buildScale(values, NAV_W, NAV_H);
  const line = values.length >= 2 ? linePoints(values, scale) : "";
  const area = values.length >= 2 ? areaPath(values, scale) : "";
  const short = !!data.warning; // backend flags short series via warning
  const first = values.length ? values[0] : null;
  const last = values.length ? values[values.length - 1] : null;

  return (
    <div className="panel" data-testid="decision-nav">
      <div className="phead">
        <span className="kicker">NAV · giá trị ròng theo ngày</span>
        {last != null && (
          <span className="num" style={{ marginLeft: "auto", fontWeight: 600 }} data-testid="nav-last">{fmtUSD(last)}</span>
        )}
      </div>

      {short && (
        <div className="hint mid" style={{ padding: "10px 16px 0", fontSize: 11, lineHeight: 1.5 }} data-testid="nav-warning">
          ⚠ {data.warning}
        </div>
      )}

      {values.length === 0 ? (
        <div className="hint" style={{ padding: "20px 16px" }} data-testid="nav-empty">Chưa có điểm NAV nào.</div>
      ) : (
        <div style={{ padding: "10px 16px 14px" }}>
          {/* short-series: explicit dots, NOT a confident trend line. */}
          <svg viewBox={`0 0 ${NAV_W} ${NAV_H}`} preserveAspectRatio="none" style={{ width: "100%", height: 150 }} role="img" aria-label={`Đường NAV, ${values.length} điểm`} data-testid="nav-svg">
            <defs>
              <linearGradient id="nav-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.18" />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
              </linearGradient>
            </defs>
            {area && <path d={area} fill="url(#nav-grad)" data-testid="nav-area" />}
            {line && (
              <polyline
                points={line}
                fill="none"
                stroke="var(--accent)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={short ? "5 4" : undefined}
                vectorEffect="non-scaling-stroke"
                data-testid="nav-line"
              />
            )}
            {/* a dot per point so a short series reads as discrete observations, not a trend */}
            {values.map((v, i) => (
              <circle key={i} cx={xAt(i, scale)} cy={yAt(v, scale)} r="3.5" fill="var(--accent)" stroke="var(--bg-0)" strokeWidth="1.5" data-testid={`nav-dot-${i}`} />
            ))}
          </svg>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <span className="hint" style={{ fontSize: 10 }}>{data.series[0] ? dayLabel(data.series[0].date) : ""}</span>
            <span className="hint faint" style={{ fontSize: 10 }} data-testid="nav-points">
              {data.points} điểm · độ tin cậy {pct01(data.confidence)}
              {first != null && last != null && first !== 0 && (
                <span style={{ marginLeft: 8 }}>· {fmtPct(((last - first) / first) * 100)}</span>
              )}
            </span>
            <span className="hint" style={{ fontSize: 10 }}>{data.series[data.series.length - 1] ? dayLabel(data.series[data.series.length - 1].date) : ""}</span>
          </div>
        </div>
      )}
    </div>
  );
}

/** verdict WORD → a tone class for the badge. This colors the verdict; it does NOT
 *  translate it to advice (the word itself is rendered verbatim). Unknown words get a
 *  neutral tone. "thin"/"weak" → de-emphasized (honest low-conviction). */
function verdictToneCls(verdict: string): string {
  const v = verdict.toLowerCase();
  if (v.includes("thin") || v.includes("weak") || v.includes("mỏng")) return "sb-dead";
  if (v.includes("strong") || v.includes("mạnh")) return "sb-act";
  return "sb-slow";
}
