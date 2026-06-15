"use client";
/* ============================================================
   EquityCurve (FE-3) — portfolio value-over-time chart on the Finance screen.
   Self-drawn SVG (line + gradient-area), REUSING lib/chart-geometry.ts (the pure
   path math written for FE-2 MarketChart — imported, NOT duplicated). Reads the
   equity curve from GET /finance/history via useFinanceHistory.

   Interactive: hover crosshair + tooltip (totalValue + day), range toggle
   (7/30/90/365 days). Optional "Snapshot hôm nay" button (POST /finance/snapshot)
   so the user can seed a point. Dark-theme via CSS tokens.

   Defensive: empty history (no snapshots yet) → friendly empty-state, never a
   broken/NaN chart; a single point → a flat honest line + dot; API error → retry.
   ============================================================ */
import { useMemo, useRef, useState } from "react";
import { useFinanceHistory, RANGE_DAYS, type RangeDays } from "@/lib/useFinanceHistory";
import { buildScale, linePoints, areaPath, xAt, yAt, indexAtX } from "@/lib/chart-geometry";
import { fmtUSD } from "@/lib/format";

const VIEW_W = 720;
const VIEW_H = 220;

/** "YYYY-MM-DD" → "DD/MM" (compact axis/tooltip label). Falls back to raw. */
function dayLabel(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!m) return day;
  return `${m[3]}/${m[2]}`;
}

export function EquityCurve() {
  const { points, status, errMsg, warning, values, days, setDays, reload, snapshotToday, snapshotting } =
    useFinanceHistory();
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const scale = useMemo(() => buildScale(values, VIEW_W, VIEW_H), [values]);
  const line = useMemo(() => linePoints(values, scale), [values, scale]);
  const area = useMemo(() => areaPath(values, scale), [values, scale]);

  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg || values.length === 0) return;
    const rect = svg.getBoundingClientRect();
    const px = rect.width > 0 ? ((e.clientX - rect.left) / rect.width) * VIEW_W : 0;
    setHoverIdx(indexAtX(px, scale));
  }
  function onLeave() { setHoverIdx(null); }

  const first = values.length ? values[0] : null;
  const last = values.length ? values[values.length - 1] : null;
  const deltaPct = first != null && last != null && first !== 0 ? ((last - first) / first) * 100 : null;
  const up = (deltaPct ?? 0) >= 0;

  const hoverP = hoverIdx != null ? points[hoverIdx] : null;
  const hoverX = hoverIdx != null ? xAt(hoverIdx, scale) : 0;
  const hoverY = hoverP ? yAt(hoverP.totalValue, scale) : 0;

  return (
    <div className="panel ecurve" data-testid="equity-curve">
      <div className="phead">
        <span className="kicker">Giá trị danh mục theo thời gian</span>
        {last != null && (
          <span className="ecurve-last" data-testid="ecurve-last">
            {fmtUSD(last)}
            {deltaPct != null && (
              <span className={`ecurve-delta ${up ? "pos" : "neg"}`} data-testid="ecurve-delta">
                {up ? "▲" : "▼"} {Math.abs(deltaPct).toFixed(2)}%
              </span>
            )}
          </span>
        )}
        <div className="ecurve-ranges" role="group" aria-label="Khoảng thời gian" style={{ marginLeft: "auto" }}>
          {RANGE_DAYS.map((r) => (
            <button
              key={r.value}
              type="button"
              className={`ecurve-range${days === r.value ? " on" : ""}`}
              aria-pressed={days === r.value}
              onClick={() => setDays(r.value as RangeDays)}
              data-testid={`ecurve-range-${r.value}`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {status === "loading" && (
        <div className="hint" style={{ padding: "26px 16px" }} data-testid="ecurve-loading">Đang tải lịch sử…</div>
      )}

      {status === "error" && (
        <div className="hint neg" style={{ padding: "26px 16px" }} data-testid="ecurve-error">
          Không tải được lịch sử: {errMsg}.
          <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && values.length === 0 && (
        <div className="ecurve-empty" data-testid="ecurve-empty">
          <div className="ecurve-empty-t">Chưa có dữ liệu lịch sử</div>
          <div className="hint" style={{ lineHeight: 1.5 }}>
            {warning ? warning : "Snapshot giá trị danh mục sẽ tích lũy theo từng ngày."}
          </div>
          <button
            className="btn sm accent"
            type="button"
            onClick={snapshotToday}
            disabled={snapshotting}
            data-testid="ecurve-snapshot-empty"
            style={{ marginTop: 10 }}
          >
            {snapshotting ? "Đang lưu…" : "+ Snapshot hôm nay"}
          </button>
        </div>
      )}

      {status === "ready" && values.length > 0 && (
        <>
          <div className="ecurve-canvas">
            <svg
              ref={svgRef}
              viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
              preserveAspectRatio="none"
              className="ecurve-svg"
              data-testid="ecurve-svg"
              onPointerMove={onMove}
              onPointerLeave={onLeave}
              role="img"
              aria-label={`Đường giá trị danh mục, ${values.length} điểm`}
            >
              <defs>
                <linearGradient id="ecurve-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={up ? "var(--green)" : "var(--red)"} stopOpacity="0.22" />
                  <stop offset="100%" stopColor={up ? "var(--green)" : "var(--red)"} stopOpacity="0" />
                </linearGradient>
              </defs>
              {area && <path d={area} fill="url(#ecurve-grad)" data-testid="ecurve-area" />}
              {line && (
                <polyline
                  points={line}
                  fill="none"
                  stroke={up ? "var(--green)" : "var(--red)"}
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  data-testid="ecurve-line"
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {/* single-point: an explicit dot so a 1-snapshot curve is visible, not invisible */}
              {values.length === 1 && (
                <circle cx={xAt(0, scale)} cy={yAt(values[0], scale)} r="4" fill={up ? "var(--green)" : "var(--red)"} data-testid="ecurve-single-dot" />
              )}
              {hoverP && (
                <g data-testid="ecurve-crosshair">
                  <line x1={hoverX} y1={0} x2={hoverX} y2={VIEW_H} stroke="var(--line-2)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
                  <circle cx={hoverX} cy={hoverY} r="3.5" fill={up ? "var(--green)" : "var(--red)"} stroke="var(--bg-0)" strokeWidth="1.5" />
                </g>
              )}
            </svg>

            {hoverP && (
              <div
                className="ecurve-tip"
                data-testid="ecurve-tooltip"
                style={{
                  left: `${(hoverX / VIEW_W) * 100}%`,
                  transform: hoverX > VIEW_W * 0.6 ? "translateX(-100%)" : "translateX(0)",
                }}
              >
                <div className="ecurve-tip-v">{fmtUSD(hoverP.totalValue)}</div>
                <div className="ecurve-tip-d">{dayLabel(hoverP.day)}</div>
              </div>
            )}
          </div>

          <div className="ecurve-foot">
            <span className="ecurve-axis" data-testid="ecurve-axis-first">{points[0] ? dayLabel(points[0].day) : ""}</span>
            <span className="hint" style={{ fontSize: 10 }}>{values.length} ngày</span>
            <span className="ecurve-axis" data-testid="ecurve-axis-last">{points[points.length - 1] ? dayLabel(points[points.length - 1].day) : ""}</span>
          </div>
        </>
      )}
    </div>
  );
}

export default EquityCurve;
