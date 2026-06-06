"use client";
/* ============================================================
   S5 — Tài chính (Finance Overview). Mirrors backend FinanceOverview:
   totalValue + change(%) + allocations[] (each with backend-computed drift +
   self-describing pnl) + dryPowder + pnlTotal.
   SELF-DESCRIBING RAW: drift/pnl are backend-computed — FE renders + formats +
   colors, NEVER recomputes. null → "—". States: loading · error · empty · data.
   (Note: the overview shape has NO trade journal / sparkline series — those live
   on other screens; click→/portfolio S6 + /journal S7.)
   ============================================================ */
import { useFinance, driftLabel } from "@/lib/useFinance";
import { useSafeRouter } from "@/lib/useNav";
import { KpiCard } from "@/components/shared/KpiCard";
import { fmtUSD, fmtSign, fmtPct } from "@/lib/format";
import { apiBase } from "@/lib/api";
import { spark } from "@/lib/spark";
import type { ChannelAlloc } from "@/lib/types";

/** P&L abs → signed USD string + tone class. 0/null → "—". */
function pnlText(abs: number | null | undefined): { text: string; cls: string } {
  if (abs == null || !Number.isFinite(abs) || abs === 0) return { text: "—", cls: "faint" };
  return { text: fmtSign(abs), cls: abs < 0 ? "neg" : "pos" };
}

export default function FinancePage() {
  const { data, status, errMsg, warning, reload } = useFinance();
  const router = useSafeRouter();

  const allocations = data.allocations ?? [];

  if (status === "loading") {
    return (
      <section className="view" data-screen="S5">
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="finance-loading">
          Đang tải tài chính…
        </div>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="view" data-screen="S5">
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="finance-error">
          Không tải được tài chính: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>
            Thử lại
          </button>
        </div>
      </section>
    );
  }

  const totalTone = (data.pnlTotal?.abs ?? 0) < 0 ? "neg" : "pos";
  const changeNeg = (data.change?.abs ?? 0) < 0;
  const changeTone = changeNeg ? "neg" : "pos";
  const sparkHtml =
    data.series && data.series.length >= 2 ? spark(data.series, "var(--accent)", 640, 130) : "";

  return (
    <section className="view" data-screen="S5" data-testid="finance-screen">
      <div className="vtitle">
        <h1>Tài chính</h1>
        <span className="sub">tổng quan danh mục</span>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="finance-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {/* Net worth + change + dry powder + open P&L */}
      <div className="grid" style={{ gridTemplateColumns: "2fr 1fr 1fr" }}>
        <div className="card glowcard" style={{ minHeight: 130 }} data-testid="finance-networth">
          {sparkHtml && (
            <div
              className="chartbg"
              style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "55%", opacity: 0.45 }}
              dangerouslySetInnerHTML={{ __html: sparkHtml }}
            />
          )}
          <div className="kicker" style={{ position: "relative" }}>Tổng tài sản</div>
          <div className="num" style={{ fontSize: 36, fontWeight: 700, position: "relative" }}>{fmtUSD(data.totalValue)}</div>
          <div className="nwd" style={{ display: "flex", gap: 14, marginTop: 4, position: "relative" }}>
            <span className={`num ${changeTone}`}>
              {changeNeg ? "▼" : "▲"} {fmtSign(data.change?.abs)} · {fmtPct(data.change?.pct ?? null)} toàn danh mục
            </span>
          </div>
        </div>
        <KpiCard label="Dry powder" value={fmtUSD(data.dryPowder)} sub="sẵn sàng DCA" />
        <KpiCard
          label="P&L mở"
          value={data.pnlTotal ? fmtSign(data.pnlTotal.abs) : "—"}
          tone={totalTone}
          sub={data.pnlTotal ? `${fmtPct(data.pnlTotal.pct)} trên vốn` : undefined}
        />
      </div>

      {/* Allocation / P&L per channel — backend drift (render-only), click→S6 */}
      <div className="panel" data-testid="finance-allocation">
        <div className="phead">
          <span className="kicker">Phân bổ &amp; P&amp;L theo kênh</span>
          <span className="link" onClick={() => router.push("/portfolio")} style={{ marginLeft: "auto" }}>
            danh mục →
          </span>
        </div>
        <div style={{ padding: "8px 16px 14px" }}>
          {allocations.length > 0 ? (
            allocations.map((a: ChannelAlloc) => {
              const drift = driftLabel(a);
              const pnl = pnlText(a.pnl?.abs);
              return (
                <div
                  key={a.channel}
                  className="mrow"
                  style={{ alignItems: "center", gap: 10, cursor: "pointer" }}
                  onClick={() => router.push(`/portfolio/${encodeURIComponent(a.channel)}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") router.push(`/portfolio/${encodeURIComponent(a.channel)}`);
                  }}
                  data-testid={`alloc-${a.channel}`}
                >
                  <span className="k" style={{ minWidth: 110 }}>{a.channel}</span>
                  <span className="barc" style={{ flex: 1 }}>
                    <i style={{ width: `${Math.max(0, Math.min(100, a.pct))}%`, background: "var(--accent)" }} />
                  </span>
                  <span className="num faint" style={{ width: 44 }}>{a.pct.toFixed(0)}%</span>
                  {drift && (
                    <span
                      className={`tagchip ${drift.alert ? "mid" : "faint"}`}
                      title="lệch so với mục tiêu (backend tính)"
                      data-testid={`drift-${a.channel}`}
                    >
                      {drift.alert ? "⚠ " : ""}{drift.text}
                    </span>
                  )}
                  <span className={`num ${pnl.cls}`} style={{ width: 80, textAlign: "right" }}>{pnl.text}</span>
                </div>
              );
            })
          ) : (
            <span className="hint">Chưa có dữ liệu phân bổ.</span>
          )}
        </div>
      </div>
    </section>
  );
}
