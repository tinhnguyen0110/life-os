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
import { useMarketChart, type ChartRange } from "@/lib/useMarketChart";
import { buildScale, linePoints, areaPath, xAt, yAt, indexAtX } from "@/lib/chart-geometry";

const VIEW_W = 720;
const VIEW_H = 240;

const RANGES: { key: ChartRange; label: string }[] = [
  { key: "7d", label: "7N" },
  { key: "30d", label: "30N" },
  { key: "all", label: "Tất cả" },
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
  const scale = useMemo(() => buildScale(closes, VIEW_W, VIEW_H), [closes]);
  const line = useMemo(() => linePoints(closes, scale), [closes, scale]);
  const area = useMemo(() => areaPath(closes, scale), [closes, scale]);

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
