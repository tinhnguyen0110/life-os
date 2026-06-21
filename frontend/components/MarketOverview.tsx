"use client";
/* ============================================================
   MarketOverview (FE-4) — multi-symbol market analytics dashboard on /market.
   Three panels driven by useMarketOverview():
     1. COMPARE table — symbols side-by-side {changePct, volatility, RSI, trend},
        client-sortable by any column.
     2. CORRELATION heatmap — pairwise Pearson matrix, cells tinted red↔green by r;
        null → grey "n/a" (honest, never mis-tinted).
     3. RELATIVE STRENGTH — each non-benchmark symbol vs BTC (derived from the
        correlation/compare data we already have — no extra per-symbol fetch).

   Defensive: each panel has its own loading/error/empty; <2 symbols → correlation
   hidden with a "cần ≥2 mã" hint (never fires the guaranteed-422 request); a
   missing metric → honest "—"; one panel's error never blanks the others.
   ============================================================ */
import { useMemo, useState } from "react";
import {
  useMarketOverview, corrCellStyle, fmtCorr,
  type CompareRow, type Trend,
} from "@/lib/useMarketOverview";

type SortKey = "symbol" | "changePct" | "volatility" | "rsi" | "trend";
type SortDir = "asc" | "desc";

const BENCHMARK = "BTC";

function num(v: number | null | undefined, digits = 2, suffix = ""): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(digits)}${suffix}`;
}
function pctText(v: number | null | undefined): { text: string; cls: string } {
  if (v == null || !Number.isFinite(v)) return { text: "—", cls: "faint" };
  return { text: `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`, cls: v < 0 ? "neg" : "pos" };
}
function trendBadge(t: Trend | null): { label: string; cls: string } {
  if (t === "up") return { label: "▲ tăng", cls: "pos" };
  if (t === "down") return { label: "▼ giảm", cls: "neg" };
  return { label: "→ phẳng", cls: "faint" };
}

/** Sort compare rows by a key+dir; null/NaN always sink to the bottom. */
function sortRows(rows: CompareRow[], key: SortKey, dir: SortDir): CompareRow[] {
  const sign = dir === "asc" ? 1 : -1;
  const val = (r: CompareRow): number | string | null => r[key] as number | string | null;
  return [...rows].sort((a, b) => {
    const av = val(a), bv = val(b);
    const aNull = av == null || (typeof av === "number" && !Number.isFinite(av));
    const bNull = bv == null || (typeof bv === "number" && !Number.isFinite(bv));
    if (aNull && bNull) return 0;
    if (aNull) return 1;   // nulls last regardless of dir
    if (bNull) return -1;
    if (typeof av === "string" && typeof bv === "string") return sign * av.localeCompare(bv);
    return sign * ((av as number) - (bv as number));
  });
}

export function MarketOverview({ symbols }: { symbols: string[] }) {
  const {
    compare, compareStatus, compareErr, compareWarning,
    correlation, corrStatus, corrErr, corrNeedsMore, reload,
  } = useMarketOverview(symbols);

  const [sortKey, setSortKey] = useState<SortKey>("changePct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function onSort(k: SortKey) {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir(k === "symbol" ? "asc" : "desc"); }
  }

  const rows = useMemo(
    () => sortRows(compare?.comparison ?? [], sortKey, sortDir),
    [compare, sortKey, sortDir],
  );

  // Relative strength vs BTC, derived from the compare rows we already fetched:
  // (symbol.changePct − BTC.changePct) → outperformance over the window.
  const relStrength = useMemo(() => {
    const list = compare?.comparison ?? [];
    const bench = list.find((r) => r.symbol === BENCHMARK);
    if (!bench || bench.changePct == null) return [];
    return list
      .filter((r) => r.symbol !== BENCHMARK && r.changePct != null)
      .map((r) => ({ symbol: r.symbol, delta: (r.changePct as number) - (bench.changePct as number) }))
      .sort((a, b) => b.delta - a.delta);
  }, [compare]);

  return (
    <div className="mov" data-testid="market-overview">
      {/* ── COMPARE TABLE ─────────────────────────────────────────────── */}
      <div className="panel mov-panel" data-testid="mov-compare">
        <div className="phead">
          <span className="kicker">So sánh đa mã</span>
          {compare?.comparison && <span className="hint" style={{ marginLeft: "auto" }}>{compare.comparison.length} mã · {Math.round((compare.window_hours ?? 0) / 24)}N</span>}
        </div>
        {compareStatus === "loading" && <div className="hint" style={{ padding: "16px" }} data-testid="mov-compare-loading">Đang tải so sánh…</div>}
        {compareStatus === "error" && (
          <div className="hint neg" style={{ padding: "16px" }} data-testid="mov-compare-error">
            Lỗi tải so sánh: {compareErr}.
            <button className="btn sm" type="button" style={{ marginLeft: 8 }} onClick={reload}>Thử lại</button>
          </div>
        )}
        {compareStatus === "ready" && rows.length === 0 && (
          <div className="hint" style={{ padding: "16px" }} data-testid="mov-compare-empty">Chưa có dữ liệu so sánh.</div>
        )}
        {compareStatus === "ready" && rows.length > 0 && (
          <table className="mov-table" data-testid="mov-compare-table" aria-label="So sánh đa mã — biến động, RSI, xu hướng">
            <thead>
              <tr>
                {([["symbol", "Mã"], ["changePct", "Δ% kỳ"], ["volatility", "Biến động"], ["rsi", "RSI"], ["trend", "Xu hướng"]] as [SortKey, string][]).map(([k, label]) => (
                  <th
                    key={k}
                    className={`mov-th${sortKey === k ? " on" : ""}`}
                    onClick={() => onSort(k)}
                    data-testid={`mov-sort-${k}`}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSort(k); } }}
                  >
                    {label}{sortKey === k ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const chg = pctText(r.changePct);
                const tb = trendBadge(r.trend);
                return (
                  <tr key={r.symbol} data-testid={`mov-row-${r.symbol}`}>
                    <td className="pn">{r.symbol}</td>
                    <td className={`num ${chg.cls}`}>{chg.text}</td>
                    <td className="num">{num(r.volatility, 3)}</td>
                    <td className="num">{num(r.rsi, 1)}</td>
                    <td className={tb.cls}>{tb.label}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {compareWarning && <div className="mov-warn" data-testid="mov-compare-warning">⚠ {compareWarning}</div>}
      </div>

      {/* ── CORRELATION HEATMAP ───────────────────────────────────────── */}
      <div className="panel mov-panel" data-testid="mov-correlation">
        <div className="phead"><span className="kicker">Tương quan (Pearson)</span></div>
        {corrNeedsMore && (
          <div className="hint" style={{ padding: "16px" }} data-testid="mov-corr-needmore">
            Cần ≥2 mã để tính tương quan.
          </div>
        )}
        {!corrNeedsMore && corrStatus === "loading" && <div className="hint" style={{ padding: "16px" }} data-testid="mov-corr-loading">Đang tải tương quan…</div>}
        {!corrNeedsMore && corrStatus === "error" && (
          <div className="hint neg" style={{ padding: "16px" }} data-testid="mov-corr-error">
            Lỗi tải tương quan: {corrErr}.
            <button className="btn sm" type="button" style={{ marginLeft: 8 }} onClick={reload}>Thử lại</button>
          </div>
        )}
        {!corrNeedsMore && corrStatus === "ready" && correlation && (
          <div className="mov-heatwrap">
            <table className="mov-heat" data-testid="mov-heatmap" aria-label="Tương quan Pearson giữa các mã">
              <thead>
                <tr>
                  <th className="mov-heat-corner" />
                  {correlation.symbols.map((s) => <th key={s} className="mov-heat-h">{s}</th>)}
                </tr>
              </thead>
              <tbody>
                {correlation.symbols.map((rowSym) => (
                  <tr key={rowSym}>
                    <th className="mov-heat-h">{rowSym}</th>
                    {correlation.symbols.map((colSym) => {
                      const r = correlation.matrix[rowSym]?.[colSym] ?? null;
                      const st = corrCellStyle(r);
                      return (
                        <td
                          key={colSym}
                          className={`mov-heat-cell${st.isNA ? " na" : ""}`}
                          style={{ background: st.background, color: st.color }}
                          data-testid={`mov-cell-${rowSym}-${colSym}`}
                          title={`${rowSym}↔${colSym}: ${fmtCorr(r)}`}
                        >
                          {st.isNA ? "n/a" : fmtCorr(r)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── RELATIVE STRENGTH vs BTC ──────────────────────────────────── */}
      <div className="panel mov-panel" data-testid="mov-relstrength">
        <div className="phead"><span className="kicker">Sức mạnh tương đối vs {BENCHMARK}</span></div>
        {compareStatus !== "ready" ? (
          <div className="hint" style={{ padding: "16px" }} data-testid="mov-rs-pending">{compareStatus === "error" ? "—" : "Đang tải…"}</div>
        ) : relStrength.length === 0 ? (
          <div className="hint" style={{ padding: "16px" }} data-testid="mov-rs-empty">Không đủ dữ liệu (cần {BENCHMARK} + ≥1 mã khác).</div>
        ) : (
          <div className="mov-rs" data-testid="mov-rs-list">
            {relStrength.map((r) => {
              const strong = r.delta >= 0;
              return (
                <div className="mov-rs-row" key={r.symbol} data-testid={`mov-rs-${r.symbol}`}>
                  <span className="pn">{r.symbol}</span>
                  <span className={`mov-rs-bar ${strong ? "pos" : "neg"}`}>
                    <span className="mov-rs-fill" style={{ width: `${Math.min(100, Math.abs(r.delta))}%` }} />
                  </span>
                  <span className={`num ${strong ? "pos" : "neg"}`}>
                    {strong ? "mạnh hơn" : "yếu hơn"} {r.delta >= 0 ? "+" : ""}{r.delta.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default MarketOverview;
