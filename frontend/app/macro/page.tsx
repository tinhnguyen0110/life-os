"use client";
/* ============================================================
   Macro context view · /macro (FE-5). Read-only: Fed funds / CPI / DXY cards —
   latest value + DESCRIPTIVE trend (up/down/flat, NO forecast/advice) + a source
   badge + a small sparkline from /macro/history (chart-geometry reuse).

   HONEST-MIRROR GATE: source="mock" → the mock badge + the backend warning show
   VERBATIM so the user never mistakes placeholders for live FRED data.
   NEUTRAL: trend is descriptive only — the FE editorializes nothing.
   States: loading · error (page gate) · empty · data. Sparkline is fail-soft
   (a card renders even if its history won't load).
   ============================================================ */
import { useEffect, useState } from "react";
import { useMacro, type MacroIndicator, type MacroTrend } from "@/lib/useMacro";
import { buildScale, linePoints } from "@/lib/chart-geometry";

const TREND_META: Record<MacroTrend, { arrow: string; cls: string; label: string }> = {
  up: { arrow: "▲", cls: "pos", label: "tăng" },
  down: { arrow: "▼", cls: "neg", label: "giảm" },
  flat: { arrow: "▬", cls: "mut", label: "đi ngang" },
};

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="macro-spark-empty faint" data-testid="macro-spark-empty">—</div>;
  const W = 120, H = 30;
  const scale = buildScale(values, W, H);
  const pts = linePoints(values, scale);
  const rising = values[values.length - 1] >= values[0];
  return (
    <svg className="macro-spark" viewBox={`0 0 ${W} ${H}`} width={W} height={H} data-testid="macro-spark" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={rising ? "var(--green)" : "var(--red)"} strokeWidth={1.5} />
    </svg>
  );
}

function IndicatorCard({ ind, loadHistory }: { ind: MacroIndicator; loadHistory: (i: string, d?: number) => Promise<number[]> }) {
  const [series, setSeries] = useState<number[]>([]);
  useEffect(() => {
    let alive = true;
    loadHistory(ind.indicator, 30).then((s) => { if (alive) setSeries(s); });
    return () => { alive = false; };
  }, [ind.indicator, loadHistory]);

  const t = TREND_META[ind.trend] ?? TREND_META.flat;
  const isMock = ind.source === "mock";
  const valueStr = `${ind.latest.toLocaleString("en-US", { maximumFractionDigits: 2 })}${ind.unit === "%" ? "%" : ""}`;

  return (
    <div className="macro-card" data-testid="macro-card" data-indicator={ind.indicator}>
      <div className="macro-card-head">
        <span className="macro-card-label">{ind.label}</span>
        {isMock && <span className="macro-badge-mock" data-testid="macro-badge-mock" title="dữ liệu mock — không phải nguồn live">mock</span>}
      </div>
      <div className="macro-card-val num" data-testid="macro-val">{valueStr}</div>
      <div className="macro-card-trend">
        <span className={t.cls} data-testid="macro-trend">{t.arrow} {t.label}</span>
        {ind.change != null && (
          <span className="faint num" style={{ marginLeft: 8 }}>
            {ind.change >= 0 ? "+" : ""}{ind.change.toLocaleString("en-US", { maximumFractionDigits: 2 })}
          </span>
        )}
      </div>
      <Sparkline values={series} />
      <div className="macro-card-foot faint">cập nhật {ind.asOf} · nguồn {ind.source}</div>
    </div>
  );
}

export default function MacroPage() {
  const { overview, status, errMsg, warning, reload, loadHistory } = useMacro();

  return (
    <section className="view" data-screen="MACRO" data-testid="macro-screen">
      <div className="vtitle">
        <h1>Macro</h1>
        <span className="sub">bối cảnh vĩ mô — Fed · CPI · DXY (mô tả xu hướng, không khuyến nghị)</span>
      </div>

      {/* mock-data warning — verbatim from the backend (honest-mirror gate) */}
      {warning && (
        <div className="panel" style={{ padding: "10px 14px", marginBottom: 12 }} data-testid="macro-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {status === "loading" ? (
        // #71: a skeleton grid (placeholder cards) instead of a blank "loading"
        // line, so the layout appears immediately while the macro fetch (~1-2s,
        // slower cold from FRED) resolves — no blank-hang.
        <div className="macro-grid" data-testid="macro-loading" aria-busy="true">
          {Array.from({ length: 6 }).map((_, i) => (
            <div className="card macro-skeleton" key={i} style={{ padding: "14px 16px", minHeight: 96 }} aria-hidden="true">
              <div className="sk-line" style={{ width: "55%" }} />
              <div className="sk-line" style={{ width: "40%", height: 22, marginTop: 10 }} />
              <div className="sk-line" style={{ width: "70%", marginTop: 12 }} />
            </div>
          ))}
        </div>
      ) : status === "error" ? (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="macro-error">
          {errMsg || "Không tải được macro."}
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      ) : overview.indicators.length === 0 ? (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="macro-empty">
          Chưa có chỉ số macro nào.
        </div>
      ) : (
        <div className="macro-grid" data-testid="macro-grid">
          {overview.indicators.map((ind) => (
            <IndicatorCard key={ind.indicator} ind={ind} loadHistory={loadHistory} />
          ))}
        </div>
      )}
    </section>
  );
}
