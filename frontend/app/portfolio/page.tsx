"use client";
/* ============================================================
   S6 — Portfolio LIST. Ported from mock screens-finance.js SCREENS.portfolio.
   Closes the nav stub. Data from GET /finance (reuse) — render-only:
   value/pct/drift/pnl are backend-computed (allocations[]); FE formats + colors.
   - header (N vị thế / M kênh from holdings/allocations counts)
   - allocation donut + legend (allocations[] value/pct)
   - holdings table (channel/symbol/qty/avgCost per holding) — current/pnl are
     CHANNEL-level (holdings[] carry no per-row price) → show the channel pnl,
     honestly labeled; each row → /portfolio/[channel] (existing detail).
   - "Thêm vị thế" → POST /finance/holdings (shared Field form, per-field 422, fail-closed).
   States: loading · error · empty · ready.
   ============================================================ */
import { useMemo, useState } from "react";
import { usePortfolio } from "@/lib/usePortfolio";
import { useSafeRouter } from "@/lib/useNav";
import { Field, TextInput, NumberInput, Select } from "@/components/shared/Field";
import { donut } from "@/lib/spark";
import { fmtUSD, fmtSign, fmtPct, relativeTime } from "@/lib/format";
import { apiBase } from "@/lib/api";
import { PortfolioNavLine } from "@/components/PortfolioNavLine";
import type { Holding, ChannelAlloc, HoldingInput } from "@/lib/types";

const CHANNEL_COLOR: Record<string, string> = {
  crypto: "var(--accent)", etf: "#4DA6FF", vn: "#a877ff", dry: "#4a3a2a",
};
const CHANNEL_LABEL: Record<string, string> = {
  crypto: "Crypto", etf: "ETF / Chứng khoán", vn: "Cổ phiếu VN", dry: "Dry powder",
};
const CHANNELS = ["crypto", "etf", "vn", "dry"];

function pnlText(abs: number | null | undefined): { text: string; cls: string } {
  if (abs == null || !Number.isFinite(abs) || abs === 0) return { text: "—", cls: "faint" };
  return { text: fmtSign(abs), cls: abs < 0 ? "neg" : "pos" };
}

/** 24h change % → signed text + tone. null (no series) → "—". render-only. */
function changeText(pct: number | null | undefined): { text: string; cls: string } {
  if (pct == null || !Number.isFinite(pct)) return { text: "—", cls: "faint" };
  return { text: fmtPct(pct), cls: pct < 0 ? "neg" : pct > 0 ? "pos" : "faint" };
}

/** current unit price → compact USD. Handles sub-cent coins (PEPE ~$3e-6) without
 *  rounding to $0. null (unpriceable / dust) → "—". */
function fmtPrice(price: number | null | undefined): string {
  if (price == null || !Number.isFinite(price)) return "—";
  if (price === 0) return "$0";
  const abs = Math.abs(price);
  if (abs >= 1) return fmtUSD(price);
  // sub-$1: show enough significant digits so a micro-cap price isn't "$0".
  const digits = abs >= 0.01 ? 4 : abs >= 0.0001 ? 6 : 8;
  return `$${price.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: 2 })}`;
}

export default function PortfolioPage() {
  const { data, status, errMsg, warning, reload, addHolding } = usePortfolio();
  const router = useSafeRouter();
  const [showAdd, setShowAdd] = useState(false);
  const [chanFilter, setChanFilter] = useState<string>("all");

  const allHoldings = data.holdings ?? [];
  const holdings = chanFilter === "all" ? allHoldings : allHoldings.filter((h) => h.channel === chanFilter);
  const allocations = data.allocations ?? [];
  // which channel tabs to show: "all" + the channels actually held (order: crypto/etf/vn/dry).
  const heldChannels = CHANNELS.filter((c) => allHoldings.some((h) => h.channel === c));
  // channel → its allocation (for the per-row channel pnl, honestly labeled).
  const allocByChannel = useMemo(() => {
    const m: Record<string, ChannelAlloc> = {};
    for (const a of allocations) m[a.channel] = a;
    return m;
  }, [allocations]);
  // donut segments from allocations with value>0.
  const segs = allocations
    .filter((a) => a.value > 0)
    .map((a) => ({ pct: a.pct, color: CHANNEL_COLOR[a.channel] ?? "var(--accent)" }));
  const channelCount = allocations.filter((a) => a.value > 0).length;

  return (
    <section className="view" data-screen="S6" data-testid="portfolio-screen">
      <div className="vtitle">
        <h1>Danh mục</h1>
        <span className="sub" data-testid="portfolio-counts">{allHoldings.length} vị thế · {channelCount} kênh</span>
        <span className="sp" />
        {/* channel filter tabs — only when >1 channel held (a single channel needs no filter) */}
        {heldChannels.length > 1 && (
          <div className="tabs" data-testid="portfolio-filter">
            <span className={`tab${chanFilter === "all" ? " on" : ""}`} onClick={() => setChanFilter("all")} data-testid="filter-all">Tất cả</span>
            {heldChannels.map((c) => (
              <span key={c} className={`tab${chanFilter === c ? " on" : ""}`} onClick={() => setChanFilter(c)} data-testid={`filter-${c}`}>
                {CHANNEL_LABEL[c] ?? c}
              </span>
            ))}
          </div>
        )}
        <button className="btn accent" type="button" onClick={() => setShowAdd((v) => !v)} data-testid="portfolio-add-toggle">
          + Thêm vị thế
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="portfolio-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {showAdd && <AddHoldingForm onAdd={addHolding} onDone={() => setShowAdd(false)} />}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="portfolio-loading">Đang tải danh mục…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="portfolio-error">
          Không tải được danh mục: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <div className="grid" style={{ gridTemplateColumns: "300px 1fr", alignItems: "start" }}>
          {/* allocation donut + legend */}
          <div className="card" style={{ alignItems: "center", gap: 14 }} data-testid="portfolio-donut">
            <div className="kicker" style={{ alignSelf: "flex-start" }}>Phân bổ</div>
            {segs.length > 0 ? (
              <>
                <div style={{ position: "relative", display: "grid", placeItems: "center" }}>
                  <span dangerouslySetInnerHTML={{ __html: donut(segs) }} />
                  <div style={{ position: "absolute", textAlign: "center" }}>
                    <div className="num" style={{ fontSize: 20, fontWeight: 700 }}>{fmtUSD(data.totalValue)}</div>
                    <div className="hint">tổng</div>
                  </div>
                </div>
                <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 7 }}>
                  {allocations.filter((a) => a.value > 0).map((a) => (
                    <div key={a.channel} style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--mono)", fontSize: 11.5 }} data-testid={`legend-${a.channel}`}>
                      <i style={{ width: 9, height: 9, borderRadius: 2, background: CHANNEL_COLOR[a.channel] ?? "var(--accent)" }} />
                      <span className="mut">{CHANNEL_LABEL[a.channel] ?? a.channel}</span>
                      <span style={{ marginLeft: "auto", color: "var(--tx-0)" }}>{a.pct.toFixed(0)}%</span>
                      <span className="faint" style={{ width: 70, textAlign: "right" }}>{fmtUSD(a.value)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <span className="hint" style={{ padding: "24px 8px", textAlign: "center" }} data-testid="portfolio-donut-empty">Chưa có phân bổ nào (toàn bộ giá trị = 0).</span>
            )}
          </div>

          {/* holdings table — per-coin P&L (backend-computed, null-safe "—" for
              basis-less coins like USDT) + channel P&L kept distinct. */}
          <div className="panel" style={{ overflow: "hidden" }}>
            <div className="phead">
              <span className="kicker">Vị thế</span>
              <span className="hint" style={{ marginLeft: "auto" }}>P&amp;L từng mã (—  = không có giá vốn) · P&amp;L kênh tách riêng</span>
            </div>
            {holdings.length === 0 ? (
              <div className="hint" style={{ padding: "28px 16px", textAlign: "center" }} data-testid="portfolio-empty">
                {allHoldings.length === 0
                  ? 'Chưa có vị thế nào. Bấm "Thêm vị thế" để ghi nhận khoản đầu tư đầu tiên.'
                  : "Không có vị thế nào trong kênh này. Thử bỏ bộ lọc."}
              </div>
            ) : (
              <table className="dtable" data-testid="portfolio-table">
                <thead>
                  <tr>
                    <th>Kênh</th><th>Mã</th><th>Số lượng</th><th>Giá hiện tại</th><th>24h</th>
                    <th>Giá trị</th><th>P&amp;L mã</th><th>P&amp;L kênh</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h: Holding) => {
                    const alloc = allocByChannel[h.channel];
                    const chanPnl = pnlText(alloc?.pnl?.abs);
                    // per-coin P&L (backend-computed) — null for basis-less coins → "—".
                    const coinPnl = pnlText(h.pnl?.abs);
                    const chg = changeText(h.changePct);
                    return (
                      <tr
                        key={`${h.channel}-${h.symbol}`}
                        style={{ cursor: "pointer" }}
                        onClick={() => router.push(`/portfolio/${encodeURIComponent(h.channel)}`)}
                        data-testid={`holding-${h.symbol}`}
                      >
                        <td>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                            <i style={{ width: 8, height: 8, borderRadius: 2, background: CHANNEL_COLOR[h.channel] ?? "var(--accent)" }} />
                            {CHANNEL_LABEL[h.channel] ?? h.channel}
                          </span>
                        </td>
                        <td className="pn">
                          {h.symbol}
                          {h.isDust && <span className="tagchip faint" style={{ marginLeft: 6, fontSize: 9 }} data-testid={`dust-${h.symbol}`}>dust ×{h.count ?? "?"}</span>}
                        </td>
                        <td className="num">{h.qty.toLocaleString()}</td>
                        <td className="num faint" data-testid={`price-${h.symbol}`}>{fmtPrice(h.price)}</td>
                        <td className={`num ${chg.cls}`} data-testid={`chg-${h.symbol}`}>{chg.text}</td>
                        <td className="num" data-testid={`value-${h.symbol}`}>{fmtUSD(h.usdValue)}</td>
                        <td className={`num ${coinPnl.cls}`} title="P&L của riêng mã này (backend tính từ giá vốn của mã) — — khi mã không có giá vốn (vd: stablecoin)" data-testid={`coinpnl-${h.symbol}`}>
                          {coinPnl.text}{h.pnl?.pct != null ? <span className="faint" style={{ marginLeft: 6, fontSize: 11 }}>{fmtPct(h.pnl.pct)}</span> : null}
                        </td>
                        <td className={`num ${chanPnl.cls}`} title="P&L của cả kênh (backend tính) — chi tiết từng mã trong trang kênh">
                          {chanPnl.text}{alloc?.pnl?.pct != null ? <span className="faint" style={{ marginLeft: 6, fontSize: 11 }}>{fmtPct(alloc.pnl.pct)}</span> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* NAV line over time (GET /decision/nav-history) — short-series honest. */}
      {status === "ready" && <PortfolioNavLine />}
    </section>
  );
}

/** Add-holding form — POST /finance/holdings via the shared Field set, per-field 422
 *  echo, FAIL-CLOSED (parent refetches on success). */
function AddHoldingForm({ onAdd, onDone }: { onAdd: ReturnType<typeof usePortfolio>["addHolding"]; onDone: () => void }) {
  const [channel, setChannel] = useState("crypto");
  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState<number | "">("");
  const [avgCost, setAvgCost] = useState<number | "">("");
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setErrs({}); setFormErr(null);
    // client-side: only the constraints the backend ALSO enforces (required fields).
    const localErrs: Record<string, string> = {};
    if (symbol.trim() === "") localErrs.symbol = "bắt buộc";
    if (qty === "") localErrs.qty = "bắt buộc";
    if (avgCost === "") localErrs.avgCost = "bắt buộc";
    if (Object.keys(localErrs).length) { setErrs(localErrs); return; }

    setBusy(true);
    const input: HoldingInput = { channel, symbol: symbol.trim(), qty: qty as number, avgCost: avgCost as number };
    const res = await onAdd(input);
    setBusy(false);
    if (res.ok) { onDone(); }
    else if (res.fieldErrors) { setErrs(res.fieldErrors); }
    else { setFormErr(res.formError ?? "thêm vị thế thất bại"); }
  }

  return (
    <div className="panel" style={{ padding: "16px 18px" }} data-testid="portfolio-add-form">
      <div className="kicker" style={{ marginBottom: 12 }}>Thêm vị thế mới</div>
      {formErr && <div className="hint neg" style={{ marginBottom: 10 }} data-testid="add-form-error">⚠ {formErr}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 12, alignItems: "end" }}>
        <Field label="Kênh" htmlFor="add-channel" error={errs.channel} testId="add-channel">
          <Select id="add-channel" value={channel} onChange={(v) => { setChannel(v); setErrs((e) => ({ ...e, channel: "" })); }} options={CHANNELS.map((c) => ({ value: c, label: CHANNEL_LABEL[c] ?? c }))} disabled={busy} invalid={!!errs.channel} testId="add-channel-input" />
        </Field>
        <Field label="Mã" htmlFor="add-symbol" error={errs.symbol} testId="add-symbol">
          <TextInput id="add-symbol" value={symbol} onChange={(v) => { setSymbol(v); setErrs((e) => ({ ...e, symbol: "" })); }} placeholder="BTC" maxLength={20} disabled={busy} invalid={!!errs.symbol} testId="add-symbol-input" />
        </Field>
        <Field label="Số lượng" htmlFor="add-qty" error={errs.qty} testId="add-qty">
          <NumberInput id="add-qty" value={qty} onChange={(v) => { setQty(v); setErrs((e) => ({ ...e, qty: "" })); }} min={0} disabled={busy} invalid={!!errs.qty} testId="add-qty-input" />
        </Field>
        <Field label="Giá vốn" htmlFor="add-avgCost" error={errs.avgCost} testId="add-avgCost">
          <NumberInput id="add-avgCost" value={avgCost} onChange={(v) => { setAvgCost(v); setErrs((e) => ({ ...e, avgCost: "" })); }} min={0} disabled={busy} invalid={!!errs.avgCost} testId="add-avgCost-input" />
        </Field>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn accent" type="button" onClick={onSubmit} disabled={busy} data-testid="add-submit">{busy ? "…" : "Thêm"}</button>
          <button className="btn ghost" type="button" onClick={onDone} disabled={busy} data-testid="add-cancel">Huỷ</button>
        </div>
      </div>
    </div>
  );
}
