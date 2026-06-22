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
import { useState, useEffect, useCallback } from "react";
import { useFinance, driftLabel } from "@/lib/useFinance";
import { useFinanceHistory } from "@/lib/useFinanceHistory";
import { useSafeRouter } from "@/lib/useNav";
import { KpiCard } from "@/components/shared/KpiCard";
import { LoadErrorShell } from "@/components/LoadErrorShell";
import { EquityCurveView } from "@/components/EquityCurve";
import { fmtUSD, fmtSign, fmtPct, relativeTime, deltaGlyph } from "@/lib/format";
import { apiBase, getCryptoBasis, setCryptoBasis } from "@/lib/api";
import { spark } from "@/lib/spark";
import type { ChannelAlloc, CryptoBasis, PnL, PnlScope } from "@/lib/types";

/** P&L abs → signed USD string + tone class. 0/null → "—". */
function pnlText(abs: number | null | undefined): { text: string; cls: string } {
  if (abs == null || !Number.isFinite(abs) || abs === 0) return { text: "—", cls: "faint" };
  return { text: fmtSign(abs), cls: abs < 0 ? "neg" : "pos" };
}

/** The "P&L mở" sub-line, scope-aware. When pnlScope is present, the pct is shown OVER
 *  its real coverage ("−72.5% trên ~2.2% danh mục có giá vốn") + the full note as a
 *  tooltip — so the honest number can't be misread as a whole-portfolio loss. Null-safe:
 *  no pnlTotal → undefined; pnlScope absent → the bare "trên vốn" fallback. */
function pnlSubNode(
  pnlTotal: PnL | null | undefined,
  pnlScope: PnlScope | null | undefined,
): React.ReactNode {
  if (!pnlTotal) return undefined;
  const pct = fmtPct(pnlTotal.pct);
  if (pnlScope && pnlScope.coveragePct != null && Number.isFinite(pnlScope.coveragePct)) {
    return (
      <span title={pnlScope.note} data-testid="pnl-scope">
        {pct} trên ~{pnlScope.coveragePct.toFixed(1)}% danh mục có giá vốn
      </span>
    );
  }
  // pnlScope present but no coveragePct → still surface the note (honest), avoid bare "trên vốn".
  if (pnlScope?.note) {
    return (
      <span title={pnlScope.note} data-testid="pnl-scope">
        {pct} trên phần có giá vốn
      </span>
    );
  }
  return `${pct} trên vốn`; // legacy fallback (pnlScope absent)
}

/* ------------------------------------------------------------------ */
/*  CryptoBasisRow — "Vốn gốc: $X [snapshot · 2 phút trước] [✏ Sửa]" */
/*  Fetches GET /finance/crypto-basis; inline edit → PUT.              */
/* ------------------------------------------------------------------ */
function CryptoBasisRow({ onSaved }: { onSaved?: () => void }) {
  const [basis, setBasis] = useState<CryptoBasis | null>(null);
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await getCryptoBasis();
      setBasis(res.data);
    } catch {
      // silently fail — backend may not be live yet
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation(); // don't navigate to /portfolio/crypto
    setInputVal(basis?.basis != null ? String(basis.basis) : "");
    setErr(null);
    setEditing(true);
  };

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditing(false);
    setErr(null);
  };

  const handleSubmit = async (e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const v = parseFloat(inputVal);
    if (!Number.isFinite(v) || v <= 0) {
      setErr("Nhập số USD dương");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const res = await setCryptoBasis(v);
      setBasis(res.data); // reflects the server-truth basis (round-trip: PUT → re-read)
      setEditing(false);
      // FAIL-CLOSED round-trip: the basis drives the crypto channel's P&L → refetch the
      // overview so the dependent pnl reflects the new basis (not just the basis label).
      onSaved?.();
    } catch (ex) {
      setErr((ex as Error).message);
    } finally {
      setSaving(false);
    }
  };

  // Not yet fetched → show nothing (backend may be offline)
  if (basis === null) return null;

  const isManual = basis.source === "manual";
  const timeLabel = basis.setAt ? relativeTime(basis.setAt) : null;

  if (editing) {
    return (
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, flexWrap: "wrap" }}
        data-testid="basis-edit-form"
      >
        <span className="hint" style={{ fontSize: 12 }}>Vốn gốc:</span>
        <span className="hint" style={{ fontSize: 12 }}>$</span>
        <input
          type="number"
          min="0"
          step="any"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          autoFocus
          style={{
            background: "var(--surface)",
            border: "1px solid var(--accent, #FF6A33)",
            borderRadius: 4,
            color: "inherit",
            fontSize: 12,
            padding: "2px 8px",
            width: 100,
            fontFamily: "var(--font-mono, monospace)",
          }}
          data-testid="basis-input"
        />
        <button
          type="submit"
          className="btn"
          disabled={saving}
          style={{ fontSize: 11, padding: "2px 10px" }}
          data-testid="basis-save"
        >
          {saving ? "…" : "Lưu"}
        </button>
        <button
          type="button"
          className="btn"
          onClick={handleCancel}
          style={{ fontSize: 11, padding: "2px 8px", opacity: 0.6 }}
        >
          Hủy
        </button>
        {err && <span className="hint neg" style={{ fontSize: 11 }}>{err}</span>}
      </form>
    );
  }

  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}
      onClick={(e) => e.stopPropagation()}
      data-testid="basis-row"
    >
      <span className="hint" style={{ fontSize: 12 }}>Vốn gốc:</span>
      <span style={{ fontSize: 12, fontFamily: "var(--font-mono, monospace)", fontWeight: 600 }}>
        {basis.basis != null ? fmtUSD(basis.basis) : "—"}
      </span>
      <span
        className="hint"
        style={{
          fontSize: 11,
          color: isManual ? "var(--accent, #FF6A33)" : undefined,
        }}
      >
        {basis.source}{timeLabel ? ` · ${timeLabel}` : ""}
      </span>
      <button
        type="button"
        onClick={handleEdit}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--text-faint)",
          fontSize: 11,
          padding: "0 4px",
          lineHeight: 1,
        }}
        title="Sửa vốn gốc"
        data-testid="basis-edit-btn"
      >
        ✏
      </button>
    </div>
  );
}

export default function FinancePage() {
  const { data, status, errMsg, warning, reload } = useFinance();
  // #143-F1 — lift the equity-curve hook so the KPI tiles + the curve paint TOGETHER on
  // the FIRST load (no stagger where the curve is drawn but the KPIs are still skeleton).
  // The curve's data is ~always instant (stored rows) while the finance path is slower
  // cold; gating the body on BOTH-initially-ready removes the perceived split-paint.
  const history = useFinanceHistory();
  const router = useSafeRouter();

  // First-paint latch: once BOTH finance + history have been ready ONCE, the body stays
  // mounted. The range toggle inside the curve re-fetches history (status→loading) but
  // must NOT re-gate the whole page — so we latch on the INITIAL readiness only.
  const [historyFirstReady, setHistoryFirstReady] = useState(false);
  useEffect(() => {
    // history "ready" (data) OR "error" both count as "done waiting" for the first paint —
    // a history error must not pin the whole finance page on loading forever; the curve
    // renders its OWN error state inside the panel.
    if (history.status === "ready" || history.status === "error") setHistoryFirstReady(true);
  }, [history.status]);

  // Combined gate for the shared shell: keep showing the finance loading hint until the
  // finance fetch is ready AND the curve's first fetch has settled → they appear as one.
  // Finance error still shows the page error; history error after first paint is the
  // curve's own concern (handled in <EquityCurveView>), NOT the page.
  const gateStatus =
    status === "error" ? "error"
    : status === "loading" || !historyFirstReady ? "loading"
    : status; // "ready"

  const allocations = data.allocations ?? [];

  const totalTone = (data.pnlTotal?.abs ?? 0) < 0 ? "neg" : "pos";
  // #81 — net-worth day-change via the SHARED honest 3-way rule: null/flat → ▬/faint
  // (was 2-way `changeNeg ? ▼ : ▲` → a no-data or $0 day rendered a green ▲, false-gain).
  const changeGlyph = deltaGlyph(data.change?.abs);
  const sparkHtml =
    data.series && data.series.length >= 2 ? spark(data.series, "var(--accent)", 640, 130) : "";

  // #138-P1a — the loading/error branch is the shared <LoadErrorShell>; the exact
  // copy + testids + section wrapper are passed verbatim so the output is byte-identical.
  return (
    <LoadErrorShell
      status={gateStatus}
      sectionClassName="view"
      dataScreen="S5"
      loadingTestid="finance-loading"
      loadingLabel="Đang tải tài chính…"
      errorTestid="finance-error"
      errorLabel={<>Không tải được tài chính: {errMsg}. Kiểm tra backend ({apiBase}).</>}
      reload={reload}
      reloadLabel="Thử lại"
    >
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
          <div className="num" style={{ fontSize: 36, fontWeight: 700, position: "relative" }} data-amount>{fmtUSD(data.totalValue)}</div>
          <div className="nwd" style={{ display: "flex", gap: 14, marginTop: 4, position: "relative" }}>
            <span className={`num ${changeGlyph.cls}`} data-amount>
              {changeGlyph.arrow} {fmtSign(data.change?.abs)} · {fmtPct(data.change?.pct ?? null)} toàn danh mục
            </span>
          </div>
        </div>
        <KpiCard label="Dry powder" value={<span data-amount>{fmtUSD(data.dryPowder)}</span>} sub="sẵn sàng DCA" />
        <KpiCard
          label="P&L mở"
          value={<span data-amount>{data.pnlTotal ? fmtSign(data.pnlTotal.abs) : "—"}</span>}
          tone={totalTone}
          sub={pnlSubNode(data.pnlTotal, data.pnlScope)}
        />
      </div>

      {/* FE-3: portfolio value over time (equity curve from GET /finance/history).
          #143-F1: the page owns the history hook (lifted above) so the curve paints
          together with the KPIs on first load; the range toggle inside still re-fetches
          locally without re-gating the page. */}
      <EquityCurveView history={history} />

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
                <div key={a.channel}>
                  <div
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
                  {/* Cost basis sub-row — only for crypto channel */}
                  {a.channel === "crypto" && (
                    <div style={{ paddingLeft: 110, marginBottom: 4 }}>
                      <CryptoBasisRow onSaved={reload} />
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <span className="hint">Chưa có dữ liệu phân bổ.</span>
          )}
        </div>
      </div>
    </section>
    </LoadErrorShell>
  );
}
