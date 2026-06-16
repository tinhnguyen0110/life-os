"use client";
/* ============================================================
   PortfolioNavLine — the NAV (net-asset-value) line for the /portfolio screen.
   Reads GET /decision/nav-history. Self-drawn SVG line reusing chart-geometry.

   SHORT-SERIES HONESTY (load-bearing, same as the Decision cockpit's NAV panel): when
   the backend flags a short series via `warning` (only 2 points live, confidence ~0.07),
   render the warning + dashed line + discrete dots — do NOT draw a confident trend from
   a couple of points. The NAV values are backend-computed; this only renders them.
   States: loading · error (retry) · empty · short-series · ready.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getNavHistory, ApiError } from "@/lib/api";
import { buildScale, linePoints, areaPath, xAt, yAt } from "@/lib/chart-geometry";
import { fmtUSD, fmtPct } from "@/lib/format";
import type { NavHistory } from "@/lib/types";

const NAV_W = 720;
const NAV_H = 140;

function dayLabel(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  return m ? `${m[3]}/${m[2]}` : day;
}
function pct01(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

type Status = "loading" | "error" | "ready";

export function PortfolioNavLine() {
  const [data, setData] = useState<NavHistory | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getNavHistory();
        if (!alive) return;
        setData(res.data);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [nonce]);

  return (
    <div className="panel" data-testid="portfolio-nav">
      <div className="phead">
        <span className="kicker">NAV · giá trị ròng theo ngày</span>
        {data && data.series.length > 0 && (
          <span className="num" style={{ marginLeft: "auto", fontWeight: 600 }} data-testid="portfolio-nav-last">
            {fmtUSD(data.series[data.series.length - 1].nav)}
          </span>
        )}
      </div>

      {status === "loading" && (
        <div className="hint" style={{ padding: "20px 16px" }} data-testid="portfolio-nav-loading">Đang tải NAV…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "20px 16px" }} data-testid="portfolio-nav-error">
          Không tải được NAV: {errMsg}.
          <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}
      {status === "ready" && data && <NavBody data={data} />}
    </div>
  );
}

function NavBody({ data }: { data: NavHistory }) {
  const values = data.series.map((p) => p.nav);
  const scale = buildScale(values, NAV_W, NAV_H);
  const line = values.length >= 2 ? linePoints(values, scale) : "";
  const area = values.length >= 2 ? areaPath(values, scale) : "";
  const short = !!data.warning;
  const first = values.length ? values[0] : null;
  const last = values.length ? values[values.length - 1] : null;

  if (values.length === 0) {
    return <div className="hint" style={{ padding: "20px 16px" }} data-testid="portfolio-nav-empty">Chưa có điểm NAV nào.</div>;
  }

  return (
    <>
      {short && (
        <div className="hint mid" style={{ padding: "10px 16px 0", fontSize: 11, lineHeight: 1.5 }} data-testid="portfolio-nav-warning">
          ⚠ {data.warning}
        </div>
      )}
      <div style={{ padding: "10px 16px 14px" }}>
        <svg viewBox={`0 0 ${NAV_W} ${NAV_H}`} preserveAspectRatio="none" style={{ width: "100%", height: 140 }} role="img" aria-label={`Đường NAV, ${values.length} điểm`} data-testid="portfolio-nav-svg">
          <defs>
            <linearGradient id="pnav-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.18" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {area && <path d={area} fill="url(#pnav-grad)" />}
          {line && (
            <polyline
              points={line}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray={short ? "5 4" : undefined}
              vectorEffect="non-scaling-stroke"
              data-testid="portfolio-nav-line"
            />
          )}
          {values.map((v, i) => (
            <circle key={i} cx={xAt(i, scale)} cy={yAt(v, scale)} r="3.5" fill="var(--accent)" stroke="var(--bg-0)" strokeWidth="1.5" data-testid={`portfolio-nav-dot-${i}`} />
          ))}
        </svg>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
          <span className="hint" style={{ fontSize: 10 }}>{data.series[0] ? dayLabel(data.series[0].date) : ""}</span>
          <span className="hint faint" style={{ fontSize: 10 }} data-testid="portfolio-nav-points">
            {data.points} điểm · độ tin cậy {pct01(data.confidence)}
            {first != null && last != null && first !== 0 && (
              <span style={{ marginLeft: 8 }}>· {fmtPct(((last - first) / first) * 100)}</span>
            )}
          </span>
          <span className="hint" style={{ fontSize: 10 }}>{data.series[data.series.length - 1] ? dayLabel(data.series[data.series.length - 1].date) : ""}</span>
        </div>
      </div>
    </>
  );
}

export default PortfolioNavLine;
