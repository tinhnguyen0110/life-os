"use client";
/* ============================================================
   S9 — Claude Usage. Ported from mock screens-system.js SCREENS.claude.
   Sections: gauge (pct/used/cap/remaining) · 3 stats (today/avgPerDay/peak) ·
   daily-bar chart (series) · per-model segment (byModel) · per-project STUB.
   RENDER-ONLY: pct/remaining/cost backend-derived, FE formats. resetIn/weekly/
   byProject are honest STUBS (null → "—"/"sắp có", NEVER a fabricated number).
   ⚠️ types mirror frozen claude_usage/schema.py. States: loading·error·ready.
   ============================================================ */
import { useClaudeUsage } from "@/lib/useClaudeUsage";
import { fmtTokens, fmtUSD, relativeTime } from "@/lib/format";
import { apiBase } from "@/lib/api";
import { gauge } from "@/lib/spark";
import type { ModelBurn } from "@/lib/types";

/** Cache-read $ portion (RULING 2): byModel carries cacheReadTokens (self-describing-raw)
 *  → cache-read is priced at 0.1 × input-rate. Sum across models. Lets the FE show
 *  "trong đó ~$X cache-read" so the (real but heavily-discounted) composition is honest. */
const IN_RATE: Record<string, number> = { opus: 15, sonnet: 3, haiku: 1 };
function cacheReadUSD(byModel: ModelBurn[]): number {
  return byModel.reduce((sum, m) => {
    const key = (Object.keys(IN_RATE).find((k) => m.model.includes(k)) ?? "opus") as keyof typeof IN_RATE;
    return sum + (m.cacheReadTokens * 0.1 * IN_RATE[key]) / 1_000_000;
  }, 0);
}

export default function ClaudeUsagePage() {
  const { data, status, errMsg, warning, reload } = useClaudeUsage();

  if (status === "loading") {
    return (
      <section className="view" data-screen="S9">
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="usage-loading">Đang tải usage…</div>
      </section>
    );
  }
  if (status === "error" || !data) {
    return (
      <section className="view" data-screen="S9">
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="usage-error">
          Không tải được Claude usage: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      </section>
    );
  }

  const u = data;
  const maxBurn = Math.max(1, ...u.series.map((d) => d.tokens));
  const maxModel = Math.max(1, ...u.byModel.map((m) => m.total));
  const cacheUSD = cacheReadUSD(u.byModel); // RULING 2: cache-read $ portion
  const modelColors = ["var(--accent)", "var(--blue)", "var(--green)", "var(--violet)", "var(--amber)", "var(--tx-2)"];

  return (
    <section className="view" data-screen="S9" data-testid="usage-screen">
      <div className="vtitle">
        <h1>Claude Usage</h1>
        <span className="sub">{u.model} · cửa sổ 5 giờ · nguồn {u.source}</span>
        <span className="sp" />
        {/* RULING 1: PROMINENT stale badge — the screen must NOT look live when the
            cache is weeks old. Visible pill near the title, not a footnote. */}
        {u.stale && (
          <span
            className="sbadge sb-slow"
            style={{ fontSize: 11, padding: "5px 11px" }}
            data-testid="usage-stale-badge"
          >
            ⚠ dữ liệu tính đến {u.asOf} · chưa cập nhật ({relativeTime(u.asOf)})
          </span>
        )}
      </div>

      <div className="grid" style={{ gridTemplateColumns: "300px 1fr", alignItems: "start" }}>
        {/* Gauge + quota stats */}
        <div className="card" style={{ alignItems: "center", gap: 10 }} data-testid="usage-gauge">
          <div className="kicker" style={{ alignSelf: "flex-start" }}>Quota hiện tại</div>
          <div className="gauge" style={{ width: 150, height: 150 }}>
            <span dangerouslySetInnerHTML={{ __html: gauge(u.pct, "var(--accent)", 150, 12) }} />
            <div className="lab">
              <b style={{ fontSize: 34, color: "var(--accent)" }}>{u.pct}%</b>
              <span style={{ fontSize: 10 }}>đã đốt</span>
            </div>
          </div>
          {/* resetIn is a STUB (null) → honest text, no fake countdown */}
          <div className="num faint" style={{ fontSize: 12 }} data-testid="usage-reset">
            {u.resetIn ? `↻ reset trong ${u.resetIn}` : "↻ reset: chưa nối"}
          </div>
          <div className="num faint" style={{ fontSize: 11 }}>
            {fmtTokens(u.used)} / {fmtTokens(u.cap)} tokens
          </div>
          <div className="divider" style={{ width: "100%", margin: "4px 0" }} />
          <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 7 }}>
            <div className="mrow"><span className="k">Còn lại</span><span className="v num">{fmtTokens(u.remaining)}</span></div>
            <div className="mrow"><span className="k">Weekly</span><span className="v num">{u.weekly != null ? `${u.weekly}%` : "—"}</span></div>
            <div className="mrow" data-testid="usage-cost">
              <span className="k">Chi phí ước tính</span>
              <span className="v num acc">{fmtUSD(u.costUSD)}</span>
            </div>
            {/* RULING 2: cache-read breakout — most spend is heavily-discounted cache-read.
                Computed from byModel.cacheReadTokens so the composition is honest. */}
            <div className="hint" style={{ fontSize: 10.5 }} data-testid="usage-cost-cache">
              trong đó ~{fmtUSD(cacheUSD)} cache-read (giá chiết khấu)
            </div>
          </div>
        </div>

        <div className="grid" style={{ gridTemplateRows: "auto 1fr", gap: 14, alignContent: "start" }}>
          {/* 3 stats */}
          <div className="grid g-3" data-testid="usage-stats">
            <div className="stat"><span className="sl">Hôm nay</span><span className="sv">{fmtTokens(u.today)}</span><span className="sd faint">tokens đốt</span></div>
            <div className="stat"><span className="sl">Trung bình/ngày</span><span className="sv">{fmtTokens(u.avgPerDay)}</span><span className="sd faint">7 ngày qua</span></div>
            <div className="stat"><span className="sl">Đỉnh</span><span className="sv">{fmtTokens(u.peak?.tokens)}</span><span className="sd faint">{u.peak?.label ?? "—"}</span></div>
          </div>

          {/* Daily-bar chart (series) */}
          <div className="card" style={{ minHeight: 200 }} data-testid="usage-daily">
            <div className="kicker">Token đốt theo ngày</div>
            {u.series.length === 0 && <span className="hint" style={{ padding: "18px 4px" }}>Chưa có dữ liệu theo ngày.</span>}
            <div style={{ display: "flex", alignItems: "flex-end", gap: 16, flex: 1, padding: "18px 4px 0" }}>
              {u.series.map((d) => {
                const h = d.tokens > 0 ? Math.max(2, (d.tokens / maxBurn) * 130) : 2;
                const hot = d.tokens / maxBurn > 0.65;
                return (
                  <div key={d.date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8, justifyContent: "flex-end", height: "100%" }}>
                    <div style={{ width: "100%", maxWidth: 46, height: h, background: d.tokens === 0 ? "var(--bg-3)" : hot ? "var(--accent)" : "var(--accent-dim)", borderRadius: "5px 5px 0 0", boxShadow: hot ? "0 0 14px -3px var(--accent)" : undefined }} title={`${d.label}: ${fmtTokens(d.tokens)}`} />
                    <span className="num faint" style={{ fontSize: 10 }}>{d.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Per-model segment (byModel) */}
      <div className="panel" data-testid="usage-bymodel">
        <div className="phead"><span className="kicker">Đốt token theo model</span></div>
        <div style={{ padding: "8px 16px 14px" }}>
          {u.byModel.length > 0 ? (
            u.byModel.map((m, i) => (
              <div className="usebar-row" key={m.model}>
                <span className="ul">{m.model}</span>
                <span className="ub"><i style={{ width: `${(m.total / maxModel) * 100}%`, background: modelColors[i % modelColors.length] }} /></span>
                <span className="uv">{fmtTokens(m.total)}</span>
                <span className="uv acc">{fmtUSD(m.costUSD)}</span>
              </div>
            ))
          ) : (
            <span className="hint">Chưa có dữ liệu model.</span>
          )}
        </div>
      </div>

      {/* Per-project — STUB (byProject is null this build; never fabricate) */}
      <div className="panel" data-testid="usage-byproject-stub">
        <div className="phead"><span className="kicker">Đốt token theo dự án / routine</span></div>
        <div className="hint" style={{ padding: "18px 16px" }}>
          Sắp có — cần parse transcripts (xem ClaudeManager); chưa có trong stats-cache.
        </div>
      </div>
    </section>
  );
}
