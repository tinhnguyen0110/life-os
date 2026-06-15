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
import { useSafeRouter } from "@/lib/useNav";
import { KpiCard } from "@/components/shared/KpiCard";
import { EquityCurve } from "@/components/EquityCurve";
import { fmtUSD, fmtSign, fmtPct, relativeTime } from "@/lib/format";
import { apiBase, getCryptoBasis, setCryptoBasis } from "@/lib/api";
import { spark } from "@/lib/spark";
import type { ChannelAlloc, CryptoBasis } from "@/lib/types";

/** P&L abs → signed USD string + tone class. 0/null → "—". */
function pnlText(abs: number | null | undefined): { text: string; cls: string } {
  if (abs == null || !Number.isFinite(abs) || abs === 0) return { text: "—", cls: "faint" };
  return { text: fmtSign(abs), cls: abs < 0 ? "neg" : "pos" };
}

/* ------------------------------------------------------------------ */
/*  CryptoBasisRow — "Vốn gốc: $X [snapshot · 2 phút trước] [✏ Sửa]" */
/*  Fetches GET /finance/crypto-basis; inline edit → PUT.              */
/* ------------------------------------------------------------------ */
function CryptoBasisRow() {
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
      setBasis(res.data);
      setEditing(false);
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

      {/* FE-3: portfolio value over time (equity curve from GET /finance/history). */}
      <EquityCurve />

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
                      <CryptoBasisRow />
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
  );
}
