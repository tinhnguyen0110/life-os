"use client";
/* ============================================================
   MarketChart (FE-2) — price chart for a tracked market asset.
   Self-drawn SVG (NO chart lib dependency — repo has none; matches the existing
   spark.ts/donut() philosophy). Line + gradient-area of the close series from
   GET /market/ohlc/{symbol}. Interactive: hover crosshair + tooltip (price + time),
   time-range toggle (7d / 30d / all). Dark-theme via CSS tokens.

   Honest-data: the backend OHLC is close-derived (not exchange candles) and ships
   a warning — we surface it verbatim so the user knows. Empty series → empty-state,
   never a broken/NaN chart.
   ============================================================ */
import { useMemo, useRef, useState } from "react";
import { useMarketChart, RANGE_PARAMS, type ChartRange } from "@/lib/useMarketChart";
import { useMarketIndicators } from "@/lib/useMarketIndicators";
import {
  buildScale, linePoints, areaPath, xAt, yAt, indexAtX,
  resampleSeries, linePointsSparse, hasAnyValue, extendScaleRange,
} from "@/lib/chart-geometry";

const VIEW_W = 720;
const VIEW_H = 240;

const RANGES: { key: ChartRange; label: string }[] = [
  { key: "7d", label: "7N" },
  { key: "30d", label: "30N" },
  { key: "all", label: "Tất cả" },
];

/** Overlay toggles — opt-in (all OFF by default so the chart stays clean). */
type OverlayKey = "sma" | "ema" | "bollinger";
const OVERLAYS: { key: OverlayKey; label: string; color: string }[] = [
  { key: "sma", label: "SMA", color: "var(--amber)" },
  { key: "ema", label: "EMA", color: "var(--cyan, #38BDF8)" },
  { key: "bollinger", label: "BB", color: "var(--tx-2)" },
];

/** Compact price label — adapts decimals to magnitude (65,563 vs 0.4213). */
function priceLabel(v: number): string {
  if (!Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  const max = abs >= 100 ? 0 : abs >= 1 ? 2 : 4;
  return v.toLocaleString("en-US", { maximumFractionDigits: max });
}

/** Short date+time for the tooltip / axis (e.g. "15/06 09:00"). */
function tsLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${dd}/${mm} ${hh}:${mi}`;
}

export function MarketChart({ symbol }: { symbol: string | null }) {
  const { data, status, errMsg, warning, closes, range, setRange, reload } = useMarketChart(symbol);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const candles = data?.candles ?? [];

  // FE-2A: indicator overlays — opt-in toggles, all OFF by default.
  const [overlays, setOverlays] = useState<Record<OverlayKey, boolean>>({ sma: false, ema: false, bollinger: false });
  const anyOverlay = overlays.sma || overlays.ema || overlays.bollinger;
  // Indicators are fetched over the SAME hours window as the active range so their
  // series spans the same time as the candles (then resampled to candle count).
  const hours = RANGE_PARAMS[range].hours;
  const { data: indData } = useMarketIndicators(symbol, hours, anyOverlay);

  // The price scale must ALSO contain the overlay values (Bollinger upper/lower can
  // exceed the close range), else the bands clip. Collect every value that will be
  // drawn, then build one shared scale.
  const overlayRaw = useMemo(() => {
    const ind = indData?.indicators;
    const out: { sma: (number | null)[]; ema: (number | null)[]; bbU: (number | null)[]; bbM: (number | null)[]; bbL: (number | null)[] } =
      { sma: [], ema: [], bbU: [], bbM: [], bbL: [] };
    if (!ind || closes.length === 0) return out;
    const n = closes.length;
    if (overlays.sma && ind.sma) out.sma = resampleSeries(ind.sma.series, n);
    if (overlays.ema && ind.ema) out.ema = resampleSeries(ind.ema.series, n);
    if (overlays.bollinger && ind.bollinger) {
      out.bbU = resampleSeries(ind.bollinger.upper, n);
      out.bbM = resampleSeries(ind.bollinger.middle, n);
      out.bbL = resampleSeries(ind.bollinger.lower, n);
    }
    return out;
  }, [indData, overlays, closes.length]);

  const scale = useMemo(() => {
    // x-axis (n) MUST stay the candle count — build from closes only, then WIDEN the
    // y-range to fit overlay extents (Bollinger bands can exceed the close range)
    // WITHOUT changing n (else the price line compresses across too many slots).
    const base = buildScale(closes, VIEW_W, VIEW_H);
    const extra = [...overlayRaw.sma, ...overlayRaw.ema, ...overlayRaw.bbU, ...overlayRaw.bbM, ...overlayRaw.bbL];
    return extendScaleRange(base, extra);
  }, [closes, overlayRaw]);

  const line = useMemo(() => linePoints(closes, scale), [closes, scale]);
  const area = useMemo(() => areaPath(closes, scale), [closes, scale]);

  // Overlay polylines (sparse — warm-up nulls skipped). Each is "" when not drawable.
  const smaLine = useMemo(() => linePointsSparse(overlayRaw.sma, scale), [overlayRaw.sma, scale]);
  const emaLine = useMemo(() => linePointsSparse(overlayRaw.ema, scale), [overlayRaw.ema, scale]);
  const bbU = useMemo(() => linePointsSparse(overlayRaw.bbU, scale), [overlayRaw.bbU, scale]);
  const bbM = useMemo(() => linePointsSparse(overlayRaw.bbM, scale), [overlayRaw.bbM, scale]);
  const bbL = useMemo(() => linePointsSparse(overlayRaw.bbL, scale), [overlayRaw.bbL, scale]);

  // Per-overlay availability: a toggle ON but the series has no finite value (window
  // too short for the period) → mark unavailable so the UI hints instead of drawing rubbish.
  const smaAvail = hasAnyValue(overlayRaw.sma);
  const emaAvail = hasAnyValue(overlayRaw.ema);
  const bbAvail = hasAnyValue(overlayRaw.bbM);
  function overlayUnavailable(k: OverlayKey): boolean {
    if (!overlays[k]) return false;
    return k === "sma" ? !smaAvail : k === "ema" ? !emaAvail : !bbAvail;
  }
  const anyUnavailable = overlayUnavailable("sma") || overlayUnavailable("ema") || overlayUnavailable("bollinger");

  function toggleOverlay(k: OverlayKey) {
    setOverlays((prev) => ({ ...prev, [k]: !prev[k] }));
  }

  // Map a pointer event to the nearest data index (viewBox coords via getBoundingClientRect).
  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg || closes.length === 0) return;
    const rect = svg.getBoundingClientRect();
    // Guard a zero-width rect (jsdom / not-yet-laid-out) → map to the first point
    // instead of dividing by zero (which would yield NaN → no crosshair).
    const px = rect.width > 0 ? ((e.clientX - rect.left) / rect.width) * VIEW_W : 0;
    setHoverIdx(indexAtX(px, scale));
  }
  function onLeave() { setHoverIdx(null); }

  const lastClose = closes.length ? closes[closes.length - 1] : null;
  const firstClose = closes.length ? closes[0] : null;
  const deltaPct =
    firstClose != null && lastClose != null && firstClose !== 0
      ? ((lastClose - firstClose) / firstClose) * 100
      : null;
  const up = (deltaPct ?? 0) >= 0;

  const hoverC = hoverIdx != null ? candles[hoverIdx] : null;
  const hoverX = hoverIdx != null ? xAt(hoverIdx, scale) : 0;
  const hoverY = hoverC ? yAt(hoverC.close, scale) : 0;

  return (
    <div className="panel mchart" data-testid="market-chart">
      <div className="phead">
        <span className="kicker">Biểu đồ giá{symbol ? ` · ${symbol}` : ""}</span>
        {lastClose != null && (
          <span className="mchart-last" data-testid="mchart-last">
            {priceLabel(lastClose)}
            {deltaPct != null && (
              <span className={`mchart-delta ${up ? "pos" : "neg"}`} data-testid="mchart-delta">
                {up ? "▲" : "▼"} {Math.abs(deltaPct).toFixed(2)}%
              </span>
            )}
          </span>
        )}
        {/* range toggle */}
        <div className="mchart-ranges" role="group" aria-label="Khoảng thời gian" style={{ marginLeft: "auto" }}>
          {RANGES.map((r) => (
            <button
              key={r.key}
              type="button"
              className={`mchart-range${range === r.key ? " on" : ""}`}
              aria-pressed={range === r.key}
              onClick={() => setRange(r.key)}
              data-testid={`mchart-range-${r.key}`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {!symbol && (
        <div className="hint" style={{ padding: "28px 16px" }} data-testid="mchart-nosymbol">
          Chọn một mã để xem biểu đồ.
        </div>
      )}

      {symbol && status === "loading" && (
        <div className="hint" style={{ padding: "28px 16px" }} data-testid="mchart-loading">Đang tải biểu đồ…</div>
      )}

      {symbol && status === "error" && (
        <div className="hint neg" style={{ padding: "28px 16px" }} data-testid="mchart-error">
          Không tải được biểu đồ: {errMsg}.
          <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {symbol && status === "ready" && closes.length === 0 && (
        <div className="hint" style={{ padding: "28px 16px" }} data-testid="mchart-empty">
          Chưa có dữ liệu giá cho {symbol} ở khoảng này.
        </div>
      )}

      {symbol && status === "ready" && closes.length > 0 && (
        <>
          {/* FE-2A: indicator overlay toggles (opt-in). An ON overlay whose window
              is too short to compute hints "không đủ điểm" instead of drawing rubbish. */}
          <div className="mchart-overlays" data-testid="mchart-overlays">
            <span className="mchart-ov-lbl">Chỉ báo:</span>
            {OVERLAYS.map((o) => (
              <button
                key={o.key}
                type="button"
                className={`mchart-ov${overlays[o.key] ? " on" : ""}`}
                aria-pressed={overlays[o.key]}
                onClick={() => toggleOverlay(o.key)}
                data-testid={`mchart-ov-${o.key}`}
                style={overlays[o.key] ? { borderColor: o.color, color: o.color } : undefined}
              >
                <span className="mchart-ov-dot" style={{ background: o.color }} /> {o.label}
                {overlayUnavailable(o.key) && <span className="mchart-ov-warn"> ·không đủ điểm</span>}
              </button>
            ))}
          </div>

          <div className="mchart-canvas">
            <svg
              ref={svgRef}
              viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
              preserveAspectRatio="none"
              className="mchart-svg"
              data-testid="mchart-svg"
              onPointerMove={onMove}
              onPointerLeave={onLeave}
              role="img"
              aria-label={`Biểu đồ giá ${symbol}, ${closes.length} điểm`}
            >
              <defs>
                <linearGradient id="mchart-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={up ? "var(--green)" : "var(--red)"} stopOpacity="0.22" />
                  <stop offset="100%" stopColor={up ? "var(--green)" : "var(--red)"} stopOpacity="0" />
                </linearGradient>
              </defs>
              {area && <path d={area} fill="url(#mchart-grad)" data-testid="mchart-area" />}
              {/* ── FE-2A overlays (drawn UNDER the price line so price stays on top) ── */}
              {overlays.bollinger && bbAvail && bbU && bbL && (
                <g data-testid="mchart-bb">
                  <polyline points={bbU} fill="none" stroke="var(--tx-2)" strokeWidth="1" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" data-testid="mchart-bb-upper" />
                  <polyline points={bbL} fill="none" stroke="var(--tx-2)" strokeWidth="1" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" data-testid="mchart-bb-lower" />
                  {bbM && <polyline points={bbM} fill="none" stroke="var(--tx-2)" strokeWidth="1" strokeOpacity="0.7" vectorEffect="non-scaling-stroke" data-testid="mchart-bb-mid" />}
                </g>
              )}
              {overlays.sma && smaAvail && smaLine && (
                <polyline points={smaLine} fill="none" stroke="var(--amber)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" data-testid="mchart-sma" />
              )}
              {overlays.ema && emaAvail && emaLine && (
                <polyline points={emaLine} fill="none" stroke="var(--cyan, #38BDF8)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" data-testid="mchart-ema" />
              )}
              {line && (
                <polyline
                  points={line}
                  fill="none"
                  stroke={up ? "var(--green)" : "var(--red)"}
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  data-testid="mchart-line"
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {/* hover crosshair + dot */}
              {hoverC && (
                <g data-testid="mchart-crosshair">
                  <line x1={hoverX} y1={0} x2={hoverX} y2={VIEW_H} stroke="var(--line-2)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
                  <circle cx={hoverX} cy={hoverY} r="3.5" fill={up ? "var(--green)" : "var(--red)"} stroke="var(--bg-0)" strokeWidth="1.5" />
                </g>
              )}
            </svg>

            {/* tooltip (HTML overlay, positioned by % so it tracks the viewBox) */}
            {hoverC && (
              <div
                className="mchart-tip"
                data-testid="mchart-tooltip"
                style={{
                  left: `${(hoverX / VIEW_W) * 100}%`,
                  // flip tooltip to the left half when near the right edge
                  transform: hoverX > VIEW_W * 0.6 ? "translateX(-100%)" : "translateX(0)",
                }}
              >
                <div className="mchart-tip-px">{priceLabel(hoverC.close)}</div>
                <div className="mchart-tip-ts">{tsLabel(hoverC.ts)}</div>
                <div className="mchart-tip-ohlc">
                  O {priceLabel(hoverC.open)} · H {priceLabel(hoverC.high)} · L {priceLabel(hoverC.low)}
                </div>
              </div>
            )}
          </div>

          {/* x-axis endpoints + honest warning */}
          <div className="mchart-foot">
            <span className="mchart-axis" data-testid="mchart-axis-first">{candles[0] ? tsLabel(candles[0].ts) : ""}</span>
            <span className="hint" style={{ fontSize: 10 }}>{closes.length} điểm · {data?.interval}m/nến</span>
            <span className="mchart-axis" data-testid="mchart-axis-last">{candles[candles.length - 1] ? tsLabel(candles[candles.length - 1].ts) : ""}</span>
          </div>
          {warning && (
            <div className="mchart-warn" data-testid="mchart-warning">⚠ {warning}</div>
          )}
        </>
      )}
    </div>
  );
}

export default MarketChart;
