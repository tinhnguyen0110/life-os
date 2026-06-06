"use client";
/* ============================================================
   S8 — Thị trường & Cảnh báo. Ported from mock screens-finance.js SCREENS.market.
   MIRRORS backend market/schema.py (Sprint 3): quotes / triggers / macro /
   alertHistory + alert-rule config (POST/DELETE /market/alerts).
   RENDER-ONLY: changePct/distance/state are server-derived; FE formats + colors.
   null changePct → "—". States: loading · error · empty · data.
   ============================================================ */
import { useState } from "react";
import { useMarket } from "@/lib/useMarket";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { KpiCard } from "@/components/shared/KpiCard";
import { relativeTime } from "@/lib/format";
import { apiBase, ApiError } from "@/lib/api";
import { Icon } from "@/lib/icons";
import type { AssetQuote, AlertTrigger, AlertEvent, MacroSignal, AlertOp } from "@/lib/types";

function priceText(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

/** signed % → display + pos/neg class. null → "—"/faint. */
function pct(v: number | null | undefined): { text: string; cls: string } {
  if (v == null || !Number.isFinite(v)) return { text: "—", cls: "faint" };
  return { text: `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`, cls: v < 0 ? "neg" : "pos" };
}

/** trigger state → badge class + label. distance is a signed ratio (server-derived). */
const STATE_BADGE: Record<string, { cls: string; label: string }> = {
  hit: { cls: "sb-act", label: "đã chạm" },
  near: { cls: "sb-slow", label: "gần" },
  far: { cls: "sb-dead", label: "còn xa" },
};

/** macro value is a display-ready string ("38","54%","$72") — show as-is, "—" if blank. */
function macroValue(v: string): string {
  return v && v.trim() !== "" ? v : "—";
}

function triggerProximity(t: AlertTrigger): string {
  if (t.state === "hit") return "đã chạm";
  // distancePct = (threshold-price)/price*100 (signed %). Guard NaN defensively.
  if (t.distancePct == null || !Number.isFinite(t.distancePct)) return "còn xa";
  return `còn cách ${Math.abs(t.distancePct).toFixed(1)}%`;
}

export default function MarketPage() {
  const { data, status, errMsg, warning, reload, setAlert, deleteAlert, ruleIdFor } = useMarket();

  const quotes = data.quotes ?? [];
  const triggers = data.triggers ?? [];
  const macro = data.macro ?? [];
  const alertHistory = data.alertHistory ?? [];

  // Threshold config form state.
  const [fSym, setFSym] = useState("");
  const [fOp, setFOp] = useState<AlertOp>("above");
  const [fThresh, setFThresh] = useState("");
  const [formBusy, setFormBusy] = useState(false);
  const [formErr, setFormErr] = useState("");

  async function onAddAlert(e: React.FormEvent) {
    e.preventDefault();
    setFormErr("");
    const threshold = Number(fThresh);
    if (!fSym.trim() || !Number.isFinite(threshold) || threshold <= 0) {
      setFormErr("Nhập symbol + ngưỡng (> 0).");
      return;
    }
    setFormBusy(true);
    try {
      await setAlert({ symbol: fSym.trim().toUpperCase(), op: fOp, threshold });
      setFSym("");
      setFThresh("");
    } catch (err) {
      setFormErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setFormBusy(false);
    }
  }

  const quoteColumns: Column<AssetQuote>[] = [
    { key: "symbol", header: "Mã", className: "pn", cell: (q) => q.symbol },
    { key: "name", header: "Tên", className: "mut", cell: (q) => q.name },
    { key: "price", header: "Giá", className: "num", cell: (q) => priceText(q.price) },
    {
      key: "chg",
      header: "Δ%",
      cell: (q) => {
        const p = pct(q.changePct);
        return <span className={p.cls}>{p.text}</span>;
      },
    },
    { key: "src", header: "Nguồn", className: "faint", cell: (q) => q.source },
  ];

  const triggerColumns: Column<AlertTrigger>[] = [
    { key: "symbol", header: "Mã", className: "pn", cell: (t) => t.symbol },
    {
      key: "rule",
      header: "Ngưỡng",
      className: "num",
      cell: (t) => `${t.op === "above" ? "≥" : "≤"} ${priceText(t.threshold)}`,
    },
    {
      key: "state",
      header: "Trạng thái",
      cell: (t) => {
        const b = STATE_BADGE[t.state] ?? STATE_BADGE.far;
        return <span className={`sbadge ${b.cls}`}>{triggerProximity(t)}</span>;
      },
    },
    {
      key: "del",
      header: "",
      cell: (t) => {
        // Trigger rows carry no id; map symbol+op → rule id to DELETE by id.
        const rid = ruleIdFor(t.symbol, t.op);
        return (
          <button
            className="btn sm"
            type="button"
            onClick={() => rid && deleteAlert(rid).catch(() => {})}
            disabled={!rid}
            title={rid ? "Xóa trigger" : "Không tìm thấy rule id"}
            data-testid={`del-${t.symbol}-${t.op}`}
          >
            ✕
          </button>
        );
      },
    },
  ];

  return (
    <section className="view" data-screen="S8" data-testid="market-screen">
      <div className="vtitle">
        <h1>Thị trường &amp; Cảnh báo</h1>
        <span className="sub">
          {quotes.length} mã theo dõi · {triggers.length} trigger
        </span>
        <span className="sp" />
        <button
          className="btn accent"
          type="button"
          onClick={reload}
          disabled={status === "loading"}
          data-testid="market-poll"
        >
          <Icon name="i-refresh" /> Poll ngay
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="market-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {/* Macro signals row (render-only). */}
      {macro.length > 0 && (
        <div className="grid g-4" data-testid="market-macro">
          {macro.map((m: MacroSignal) => (
            <KpiCard
              key={m.name}
              label={m.name}
              value={macroValue(m.value)}
              sub={m.note || m.status}
              tone={m.status === "up" ? "pos" : m.status === "down" ? "neg" : "default"}
            />
          ))}
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1.4fr 1fr", alignItems: "start" }}>
        {/* Quotes (price table) */}
        <div className="panel" style={{ overflow: "hidden" }}>
          <div className="phead">
            <span className="kicker">Bảng giá</span>
            <span className="dot g" style={{ marginLeft: "auto" }} />
            <span className="hint">market-poll mỗi 5 phút</span>
          </div>
          {status === "loading" && (
            <div className="hint" style={{ padding: "18px 16px" }} data-testid="market-loading">
              Đang tải thị trường…
            </div>
          )}
          {status === "error" && (
            <div className="hint neg" style={{ padding: "18px 16px" }} data-testid="market-error">
              Không tải được thị trường: {errMsg}. Kiểm tra backend ({apiBase}).
              <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>
                Thử lại
              </button>
            </div>
          )}
          {status === "ready" && (
            <DataTable
              columns={quoteColumns}
              rows={quotes}
              rowKey={(q) => q.symbol}
              emptyLabel="Chưa có mã nào."
            />
          )}
        </div>

        {/* Right column: triggers + threshold form + alert history */}
        <div className="grid" style={{ gridTemplateRows: "auto auto auto", gap: 14, alignContent: "start" }}>
          <div className="panel" data-testid="market-triggers">
            <div className="phead">
              <span className="kicker">Trigger đang đặt</span>
              <span className="hint" style={{ marginLeft: "auto" }}>
                {triggers.length}
              </span>
            </div>
            <DataTable
              columns={triggerColumns}
              rows={triggers}
              // index suffix: the backend can return duplicate symbol+op rows
              // (observed live) — keep keys unique so React doesn't drop rows.
              rowKey={(t, i) => `${t.symbol}-${t.op}-${i}`}
              emptyLabel="Chưa đặt trigger nào."
            />
          </div>

          {/* Threshold config UI */}
          <div className="panel" data-testid="market-alert-form">
            <div className="phead">
              <span className="kicker">Đặt ngưỡng cảnh báo</span>
            </div>
            <form onSubmit={onAddAlert} style={{ padding: "10px 16px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
              <div className="row" style={{ gap: 8 }}>
                <input
                  className="tab"
                  style={{ flex: 1, fontFamily: "var(--mono)" }}
                  placeholder="Symbol (BTC)"
                  value={fSym}
                  onChange={(e) => setFSym(e.target.value)}
                  aria-label="Symbol"
                  data-testid="alert-symbol"
                />
                <select
                  className="tab"
                  value={fOp}
                  onChange={(e) => setFOp(e.target.value as AlertOp)}
                  aria-label="Điều kiện"
                  data-testid="alert-op"
                >
                  <option value="above">≥ above</option>
                  <option value="below">≤ below</option>
                </select>
                <input
                  className="tab"
                  style={{ width: 100, fontFamily: "var(--mono)" }}
                  placeholder="Ngưỡng"
                  inputMode="decimal"
                  value={fThresh}
                  onChange={(e) => setFThresh(e.target.value)}
                  aria-label="Ngưỡng"
                  data-testid="alert-threshold"
                />
              </div>
              {formErr && <span className="hint neg" data-testid="alert-form-error">{formErr}</span>}
              <button className="btn accent" type="submit" disabled={formBusy} data-testid="alert-submit">
                {formBusy ? "Đang lưu…" : "+ Đặt cảnh báo"}
              </button>
            </form>
          </div>

          {/* Alert history */}
          <div className="panel" data-testid="market-history">
            <div className="phead">
              <span className="kicker">Lịch sử cảnh báo</span>
              <span className="dot r" style={{ marginLeft: "auto" }} />
              <span className="hint">{alertHistory.length}</span>
            </div>
            <div style={{ padding: "8px 16px 14px" }}>
              {alertHistory.length > 0 ? (
                alertHistory.map((a: AlertEvent, i) => (
                  <div className="mrow" key={`${a.symbol}-${a.ts}-${i}`}>
                    <span className="k">
                      {a.symbol} {a.op === "above" ? "≥" : "≤"} {priceText(a.threshold)}
                    </span>
                    <span className="v mut" style={{ fontWeight: 400, fontSize: 11 }}>
                      @ {priceText(a.price)} · {relativeTime(a.ts)}
                    </span>
                  </div>
                ))
              ) : (
                <span className="hint">Chưa có cảnh báo nào kích hoạt.</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
