"use client";
/* ============================================================
   Exchange — tab-based multi-exchange overview.
   Tabs: OKX (live), Binance (coming soon stub).
   OKX tab: KPI row + balances table + positions table + sync button.
   States: loading · error · unconfigured · data.
   ============================================================ */
import { useState, useEffect, useCallback } from "react";
import { getExchange, syncExchange, apiBase } from "@/lib/api";
import { fmtUSD, fmtSign, fmtPct, relativeTime } from "@/lib/format";
import type { ExchangeOverview, OkxBalance, OkxPosition } from "@/lib/types";

/* ---------- Tab registry — push new entry here to add a sàn ---------- */
const EXCHANGE_TABS = [
  { id: "okx", label: "OKX" },
  { id: "binance", label: "Binance" },
] as const;

type TabId = (typeof EXCHANGE_TABS)[number]["id"];
type Status = "loading" | "error" | "data";

function pnlCls(v: number) {
  if (v > 0) return "pos";
  if (v < 0) return "neg";
  return "faint";
}

/** Per-coin cost-basis P&L cell from the backend's spotUpl (abs USD) + spotUplRatio
 *  (a RATIO, ×100 for %). null-safe: a no-basis coin (USDT/ETH → null) → "—", NEVER a
 *  fabricated 0/%. render-only — spotUpl is the BACKEND's number, FE formats + colors. */
function costPnl(
  spotUpl: number | null | undefined,
  spotUplRatio: number | null | undefined,
): { text: string; pct: string; cls: string; hasData: boolean } {
  if (spotUpl == null || !Number.isFinite(spotUpl)) {
    return { text: "—", pct: "", cls: "faint", hasData: false };
  }
  const cls = spotUpl > 0 ? "pos" : spotUpl < 0 ? "neg" : "faint";
  const pct =
    spotUplRatio != null && Number.isFinite(spotUplRatio) ? fmtPct(spotUplRatio * 100) : "";
  return { text: fmtSign(spotUpl), pct, cls, hasData: true };
}

/* ------------------------------------------------------------------ */
/*  OKX tab content                                                     */
/* ------------------------------------------------------------------ */
function OkxTab() {
  const [data, setData] = useState<ExchangeOverview | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await getExchange();
      setData(res.data);
      setWarning(res.warning ?? null);
      setStatus("data");
    } catch (e) {
      setErrMsg((e as Error).message);
      setStatus("error");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await syncExchange();
      setData(res.data);
      setWarning(res.warning ?? null);
    } catch (e) {
      setWarning(`Sync lỗi: ${(e as Error).message}`);
    } finally {
      setSyncing(false);
    }
  };

  if (status === "loading") {
    return (
      <div className="hint" style={{ padding: "32px 0", textAlign: "center" }} data-testid="exchange-loading">
        Đang tải OKX…
      </div>
    );
  }

  if (status === "error") {
    return (
      <div
        className="card"
        style={{ padding: "24px", textAlign: "center", borderColor: "var(--neg, #FF5C5C)" }}
        data-testid="exchange-error"
      >
        <div style={{ color: "var(--neg, #FF5C5C)", marginBottom: 8, fontWeight: 600 }}>
          Không tải được dữ liệu OKX
        </div>
        <div className="hint" style={{ fontSize: 13, marginBottom: 16 }}>
          {errMsg} — Kiểm tra backend ({apiBase})
        </div>
        <button className="btn" type="button" onClick={load}>
          Thử lại
        </button>
      </div>
    );
  }

  const overview = data!;

  if (!overview.configured) {
    return (
      <div
        className="card"
        style={{ padding: "40px 32px", textAlign: "center" }}
        data-testid="exchange-unconfigured"
      >
        <div style={{ fontSize: 36, marginBottom: 12 }}>🔑</div>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>Chưa cấu hình API key OKX</div>
        <div className="hint" style={{ marginBottom: 16, fontSize: 13 }}>
          Thêm vào <code>backend/.env</code> rồi restart backend:
        </div>
        <pre
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "12px 20px",
            textAlign: "left",
            fontSize: 13,
            display: "inline-block",
            lineHeight: 1.6,
          }}
        >
{`LIFEOS_OKX_API_KEY=your_key
LIFEOS_OKX_API_SECRET=your_secret
LIFEOS_OKX_API_PASSPHRASE=your_passphrase`}
        </pre>
        <div className="hint" style={{ marginTop: 12, fontSize: 12 }}>
          Tạo API key read-only trên OKX → Account → API Management
        </div>
      </div>
    );
  }

  /* Detect if all balances have frozen=0 → hide frozen column */
  const hasFrozen = overview.balances.some((b: OkxBalance) => b.frozen > 0);

  return (
    <>
      {/* Sync meta + button row */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
        <span className="hint" style={{ fontSize: 12 }}>
          Cập nhật {overview.syncedAt ? relativeTime(overview.syncedAt) : "chưa sync"}
        </span>
        <div style={{ flex: 1 }} />
        <button
          className="btn"
          type="button"
          onClick={handleSync}
          disabled={syncing}
          data-testid="exchange-sync-btn"
          style={{ fontSize: 13 }}
        >
          {syncing ? "Đang sync…" : "↻ Sync"}
        </button>
      </div>

      {warning && (
        <div
          className="hint"
          style={{
            marginBottom: 16,
            fontSize: 13,
            padding: "10px 14px",
            background: "color-mix(in srgb, var(--neg, #FF5C5C) 12%, transparent)",
            border: "1px solid color-mix(in srgb, var(--neg, #FF5C5C) 30%, transparent)",
            borderRadius: 8,
            color: "var(--neg, #FF5C5C)",
          }}
          data-testid="exchange-warning"
        >
          ⚠ {warning}
        </div>
      )}

      {/* KPI row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 24 }}>
        <div className="card" style={{ padding: "20px 24px" }}>
          <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-faint)", marginBottom: 8 }}>
            Tổng tài khoản
          </div>
          <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "var(--font-mono, monospace)", letterSpacing: "-0.01em" }} data-testid="exchange-total" data-amount>
            {fmtUSD(overview.totalUsdValue)}
          </div>
        </div>
        <div className="card" style={{ padding: "20px 24px" }}>
          <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-faint)", marginBottom: 8 }}>
            Số coin
          </div>
          <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "var(--font-mono, monospace)" }}>
            {overview.balances.length}
          </div>
        </div>
        <div className="card" style={{ padding: "20px 24px" }}>
          <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-faint)", marginBottom: 8 }}>
            Open Positions
          </div>
          <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "var(--font-mono, monospace)" }}>
            {overview.positions.length}
          </div>
        </div>
      </div>

      {/* Balances table */}
      <div className="card" style={{ marginBottom: 20, overflow: "hidden" }}>
        <div style={{
          padding: "14px 16px",
          fontWeight: 600,
          fontSize: 13,
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}>
          Số dư tài sản
          <span className="hint" style={{ fontSize: 12, fontWeight: 400 }}>
            {overview.balances.length} coin
          </span>
        </div>
        {overview.balances.length === 0 ? (
          <div className="hint" style={{ padding: "40px 16px", textAlign: "center" }}>
            Không có tài sản
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }} aria-label="Số dư tài sản trên sàn">
            <thead>
              <tr style={{ background: "var(--surface, rgba(255,255,255,0.03))" }}>
                <th style={{ textAlign: "left", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>
                  Coin
                </th>
                <th style={{ textAlign: "right", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>
                  Khả dụng
                </th>
                {hasFrozen && (
                  <th style={{ textAlign: "right", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>
                    Đang khóa
                  </th>
                )}
                <th style={{ textAlign: "right", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>
                  Giá trị USD
                </th>
                <th style={{ textAlign: "right", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>
                  P&amp;L (giá vốn)
                </th>
              </tr>
            </thead>
            <tbody>
              {overview.balances.map((b: OkxBalance) => {
                // #145-R1 — the "·dust" row is a backend FOLD of N sub-$0.001 coins (a
                // rollup, not a holding). Detect via the honest `isDust` flag (not string-
                // match) → render it distinctly so a user reads it as a summary, not a coin.
                const isDust = b.isDust === true;
                const isSmall = !isDust && b.usdValue != null && b.usdValue < 1;
                const pnl = costPnl(b.spotUpl, b.spotUplRatio);
                return (
                  <tr
                    key={b.symbol}
                    className="exch-bal-row"
                    style={{
                      // dust gets a stronger separator (it's a rollup boundary, not just
                      // another coin) + a fully muted look; small coins stay dimmed.
                      // NOTE: the surrounding rows use `var(--border)` which is UNDEFINED in
                      // this token system (→ no border renders) — flagged separately. The
                      // dust separator uses a REAL token (--line-2) so it actually shows.
                      borderTop: isDust ? "1px solid var(--line-2)" : "1px solid var(--border)",
                      opacity: isDust ? 0.7 : isSmall ? 0.55 : 1,
                    }}
                    data-testid={`balance-row-${b.symbol}`}
                  >
                    <td style={{ padding: "11px 16px", fontWeight: isDust ? 400 : 600, fontSize: 14 }}>
                      {isDust ? (
                        <span style={{ fontStyle: "italic", color: "var(--text-faint)" }} data-testid="balance-dust-label">
                          {b.symbol}
                          {b.count != null && (
                            <span style={{ fontSize: 11, marginLeft: 6 }}>({b.count} coin gộp)</span>
                          )}
                        </span>
                      ) : (
                        b.symbol
                      )}
                    </td>
                    <td style={{ padding: "11px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", color: "var(--text-secondary, var(--text-faint))" }}>
                      {b.available.toLocaleString("en", { maximumFractionDigits: 6 })}
                    </td>
                    {hasFrozen && (
                      <td style={{ padding: "11px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", color: "var(--text-faint)" }}>
                        {b.frozen > 0 ? b.frozen.toLocaleString("en", { maximumFractionDigits: 6 }) : "—"}
                      </td>
                    )}
                    <td style={{ padding: "11px 16px", textAlign: "right", fontWeight: 600 }}>
                      {b.usdValue != null ? fmtUSD(b.usdValue) : "—"}
                    </td>
                    {/* per-coin cost-basis P&L (backend spotUpl/spotUplRatio) — null-safe "—"
                        for a no-basis coin (USDT/stablecoin), never a fabricated 0/%. */}
                    <td
                      className={`num ${pnl.cls}`}
                      style={{ padding: "11px 16px", textAlign: "right", fontWeight: 600, fontFamily: "var(--font-mono, monospace)" }}
                      title="Lãi/lỗ chưa thực hiện theo giá vốn OKX (accAvgPx) — — khi không có giá vốn (vd stablecoin)"
                      data-testid={`balance-pnl-${b.symbol}`}
                    >
                      {pnl.text}
                      {pnl.pct && <span className="faint" style={{ marginLeft: 6, fontSize: 11 }}>{pnl.pct}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Positions table (only if any) */}
      {overview.positions.length > 0 && (
        <div className="card" style={{ overflow: "hidden" }}>
          <div style={{
            padding: "14px 16px",
            fontWeight: 600,
            fontSize: 13,
            borderBottom: "1px solid var(--border)",
          }}>
            Open Positions
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }} aria-label="Vị thế đang mở">
            <thead>
              <tr style={{ background: "var(--surface, rgba(255,255,255,0.03))" }}>
                <th style={{ textAlign: "left", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>Instrument</th>
                <th style={{ textAlign: "center", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>Side</th>
                <th style={{ textAlign: "right", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>Qty</th>
                <th style={{ textAlign: "right", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>Avg Open</th>
                <th style={{ textAlign: "right", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>Unrealized P&L</th>
                <th style={{ textAlign: "center", padding: "9px 16px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)" }}>Lev</th>
              </tr>
            </thead>
            <tbody>
              {overview.positions.map((p: OkxPosition, i: number) => (
                <tr key={`${p.instId}-${i}`} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ padding: "11px 16px", fontWeight: 600 }}>{p.instId}</td>
                  <td style={{ padding: "11px 16px", textAlign: "center" }}>
                    <span style={{
                      display: "inline-block",
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 700,
                      letterSpacing: "0.04em",
                      background: p.side === "long"
                        ? "color-mix(in srgb, var(--green, #34E08A) 15%, transparent)"
                        : "color-mix(in srgb, var(--red, #FF5C5C) 15%, transparent)",
                      color: p.side === "long" ? "var(--green, #34E08A)" : "var(--red, #FF5C5C)",
                    }}>
                      {p.side.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: "11px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)" }}>
                    {p.qty.toLocaleString("en", { maximumFractionDigits: 4 })}
                  </td>
                  <td style={{ padding: "11px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)" }}>
                    {fmtUSD(p.avgOpenPrice)}
                  </td>
                  <td style={{ padding: "11px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", fontWeight: 600 }}>
                    <span className={pnlCls(p.unrealizedPnl)}>
                      {p.unrealizedPnl >= 0 ? "+" : ""}{fmtUSD(p.unrealizedPnl)}
                    </span>
                  </td>
                  <td style={{ padding: "11px 16px", textAlign: "center", color: "var(--text-faint)", fontSize: 13 }}>
                    {p.lever}×
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Binance stub tab                                                    */
/* ------------------------------------------------------------------ */
function BinanceTab() {
  return (
    <div
      className="card"
      style={{
        padding: "60px 32px",
        textAlign: "center",
        border: "1px dashed var(--border)",
        background: "transparent",
      }}
      data-testid="binance-stub"
    >
      <div style={{ fontSize: 44, marginBottom: 16 }}>🔑</div>
      <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 8 }}>
        Binance chưa tích hợp
      </div>
      <div className="hint" style={{ fontSize: 13, maxWidth: 320, margin: "0 auto" }}>
        Coming soon — API key sẽ được cấu hình trong{" "}
        <a href="/settings" style={{ color: "var(--accent, #FF6A33)", textDecoration: "none" }}>
          Settings
        </a>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page shell — header + tab bar + routed content                     */
/* ------------------------------------------------------------------ */
export default function ExchangePage() {
  const [activeTab, setActiveTab] = useState<TabId>("okx");

  return (
    <section className="view" data-screen="exchange">
      {/* Page heading row */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 20 }}>
        <h2 style={{ margin: 0 }}>Sàn giao dịch</h2>
        <span className="hint" style={{ fontSize: 12 }}>tổng quan tài khoản</span>
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border)",
          marginBottom: 24,
          gap: 4,
        }}
        role="tablist"
        data-testid="exchange-tab-bar"
      >
        {EXCHANGE_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              data-testid={`exchange-tab-${tab.id}`}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              style={{
                background: "none",
                border: "none",
                borderBottom: isActive
                  ? "2px solid var(--accent, #FF6A33)"
                  : "2px solid transparent",
                color: isActive ? "var(--accent, #FF6A33)" : "var(--text-faint)",
                cursor: "pointer",
                fontFamily: "var(--font-sans, inherit)",
                fontSize: 14,
                fontWeight: isActive ? 600 : 400,
                padding: "6px 18px 10px",
                marginBottom: "-1px",
                transition: "color 0.15s, border-color 0.15s",
                letterSpacing: isActive ? "0.01em" : "normal",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {activeTab === "okx" && <OkxTab />}
      {activeTab === "binance" && <BinanceTab />}
    </section>
  );
}
