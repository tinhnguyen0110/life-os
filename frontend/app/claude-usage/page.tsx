"use client";
/* ============================================================
   S9 — Claude Usage · Full Report. LIVE from session transcripts (.jsonl) +
   statusline quota tee. Sections:
     1. Summary KPI row — total cost · total tokens · #projects · #models
     2. Quota card (5h gauge + 5h/7d reset + context session) · cost breakdown
     3. Daily-burn chart (7d) + 3 stats
     4. By-model table (% share, tokens, cost)
     5. By-project table (% share, tokens, msgs, cost)
   render-only; pct5h/ctx/quota live from snapshot, tokens/cost from transcripts.
   STUB fields (resetIn/weekly null) → honest "—", never fabricated.
   ============================================================ */
import { useClaudeUsage } from "@/lib/useClaudeUsage";
import { fmtTokens, fmtUSD, relativeTime } from "@/lib/format";
import { apiBase } from "@/lib/api";
import { gauge } from "@/lib/spark";
import type { ModelBurn } from "@/lib/types";

/** Cache-read $ portion: byModel carries cacheReadTokens (self-describing-raw) →
 *  priced at 0.1 × input-rate. Input rates MIRROR the official docs (backend
 *  pricing.py): opus 4.5+ = $5 (NOT the old 15), opus 4.0/4.1 = $15, sonnet 3,
 *  haiku 1, fable 10. Picks the rate by model family so the cache-read leg of the
 *  cost stays consistent with the backend total. */
const IN_RATE_NEW = { opus: 5, sonnet: 3, haiku: 1, fable: 10 } as const;
function inputRate(model: string): number {
  if (model.includes("fable")) return IN_RATE_NEW.fable;
  // deprecated opus 4.0/4.1 keep $15; every other opus (4.5+) is $5
  if (/opus-4-[01](\b|-)/.test(model)) return 15;
  if (model.includes("opus")) return IN_RATE_NEW.opus;
  if (model.includes("sonnet")) return IN_RATE_NEW.sonnet;
  if (model.includes("haiku")) return IN_RATE_NEW.haiku;
  return IN_RATE_NEW.sonnet; // fallback
}
function cacheReadUSD(byModel: ModelBurn[]): number {
  return byModel.reduce((sum, m) => {
    return sum + (m.cacheReadTokens * 0.1 * inputRate(m.model)) / 1_000_000;
  }, 0);
}

/** Short display label for a model id: drop the "claude-" prefix + dated suffix. */
function modelLabel(model: string): string {
  return model.replace(/^claude-/, "").replace(/-\d{8}$/, "");
}

const MODEL_COLORS = [
  "var(--accent)", "var(--blue)", "var(--green)", "var(--violet)", "var(--amber)", "var(--tx-2)",
];

export default function ClaudeUsagePage() {
  const { data, status, errMsg, reload } = useClaudeUsage();

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
  const totalModelTokens = Math.max(1, u.byModel.reduce((s, m) => s + m.total, 0));
  const maxModel = Math.max(1, ...u.byModel.map((m) => m.total));
  const maxProject = Math.max(1, ...u.byProject.map((p) => p.total));
  const totalProjectTokens = Math.max(1, u.byProject.reduce((s, p) => s + p.total, 0));
  const cacheUSD = cacheReadUSD(u.byModel); // RULING 2: cache-read $ portion
  const directUSD = Math.max(0, u.costUSD - cacheUSD); // input+output (non-cache) share

  return (
    <section className="view" data-screen="S9" data-testid="usage-screen">
      {/* ---- Title ---- */}
      <div className="vtitle">
        <h1>Claude Usage</h1>
        <span className="sub">
          {u.model}
          {u.tokenSource === "transcripts" ? " · token LIVE (.jsonl)" : ` · token nguồn ${u.tokenSource}`}
          {u.quotaSource === "snapshot" && " · quota LIVE"}
        </span>
        <span className="sp" />
        {u.stale && (
          <span className="sbadge sb-slow" style={{ fontSize: 11, padding: "5px 11px" }} data-testid="usage-stale-badge">
            ⚠ dữ liệu tính đến {u.asOf} · chưa cập nhật ({relativeTime(u.asOf)})
          </span>
        )}
      </div>

      {/* ---- 1. Summary KPI row ---- */}
      <div className="grid g-4" data-testid="usage-summary">
        <div className="stat">
          <span className="sl">Giá API quy đổi</span>
          <span className="sv acc">{fmtUSD(u.costUSD)}</span>
          <span className="sd faint">≈{fmtUSD(cacheUSD)} cache-read · gói sub</span>
        </div>
        <div className="stat">
          <span className="sl">Tổng token</span>
          <span className="sv">{fmtTokens(totalModelTokens)}</span>
          <span className="sd faint">in + out (mọi model)</span>
        </div>
        <div className="stat">
          <span className="sl">Dự án</span>
          <span className="sv">{u.byProject.length || "—"}</span>
          <span className="sd faint">có token Claude</span>
        </div>
        <div className="stat">
          <span className="sl">Model</span>
          <span className="sv">{u.byModel.length || "—"}</span>
          <span className="sd faint">đã dùng</span>
        </div>
      </div>

      {/* ---- 2. Quota card (5h + 7d dual gauge) + cost breakdown ---- */}
      <div className="grid" style={{ gridTemplateColumns: "340px 1fr", alignItems: "start" }}>
        {/* Quota card — two LIVE rate-limit gauges side by side: 5h + 7d (weekly).
            NOTE: per-session context is intentionally NOT shown here — the account
            quota spans many sessions, so a single session's context window would
            misleadingly read as "the quota". Context lives only in the statusline. */}
        <div className="card" style={{ gap: 14, justifyContent: "center" }} data-testid="usage-gauge">
          <div className="kicker">Quota rate-limit</div>

          {/* dual gauge: 5h | 7d */}
          <div style={{ display: "flex", justifyContent: "space-around", gap: 8 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 7 }} data-testid="usage-quota-5h">
              <div className="gauge" style={{ width: 124, height: 124 }}>
                <span dangerouslySetInnerHTML={{ __html: gauge(u.pct5h ?? u.pct, "var(--accent)", 124, 11) }} />
                <div className="lab">
                  <b style={{ fontSize: 28, color: "var(--accent)" }}>{u.pct5h ?? u.pct}%</b>
                  <span style={{ fontSize: 9 }}>5 giờ</span>
                </div>
              </div>
              <div className="num faint" style={{ fontSize: 10.5 }} data-testid="usage-reset">
                {u.resetIn ? `↻ ${u.resetIn}` : "chưa nối"}
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 7 }} data-testid="usage-quota-7d">
              <div className="gauge" style={{ width: 124, height: 124 }}>
                <span dangerouslySetInnerHTML={{ __html: gauge(u.weekly ?? 0, "var(--blue)", 124, 11) }} />
                <div className="lab">
                  <b style={{ fontSize: 28, color: "var(--blue)" }}>{u.weekly != null ? `${u.weekly}%` : "—"}</b>
                  <span style={{ fontSize: 9 }}>7 ngày</span>
                </div>
              </div>
              <div className="num faint" style={{ fontSize: 10.5 }}>
                {u.resetWeek ? `↻ ${u.resetWeek}` : "—"}
              </div>
            </div>
          </div>
        </div>

        {/* Right column: cost breakdown + daily chart */}
        <div className="grid" style={{ gridTemplateRows: "auto auto", gap: 14, alignContent: "start" }}>
          {/* Cost breakdown card */}
          <div className="card" data-testid="usage-cost-breakdown">
            <div className="phead" style={{ padding: 0, border: 0, marginBottom: 12 }}>
              <span className="kicker">Giá API quy đổi</span>
              <span className="num acc" style={{ marginLeft: "auto", fontSize: 22, fontWeight: 700 }}>{fmtUSD(u.costUSD)}</span>
            </div>
            {/* stacked bar: direct (input+output) vs cache-read */}
            <div style={{ display: "flex", height: 10, borderRadius: 5, overflow: "hidden", background: "var(--bg-3)" }}>
              <div style={{ width: `${(directUSD / Math.max(1, u.costUSD)) * 100}%`, background: "var(--accent)" }} title={`direct ${fmtUSD(directUSD)}`} />
              <div style={{ width: `${(cacheUSD / Math.max(1, u.costUSD)) * 100}%`, background: "var(--blue)" }} title={`cache-read ${fmtUSD(cacheUSD)}`} />
            </div>
            <div style={{ display: "flex", gap: 20, marginTop: 12, fontFamily: "var(--mono)", fontSize: 11.5 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <i style={{ width: 9, height: 9, borderRadius: 2, background: "var(--accent)" }} />
                <span className="mut">input + output</span>
                <b style={{ color: "var(--tx-0)" }} data-testid="usage-cost-direct">{fmtUSD(directUSD)}</b>
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <i style={{ width: 9, height: 9, borderRadius: 2, background: "var(--blue)" }} />
                <span className="mut">cache-read</span>
                <b style={{ color: "var(--tx-0)" }} data-testid="usage-cost-cache">{fmtUSD(cacheUSD)}</b>
              </span>
            </div>
            <div className="hint" style={{ fontSize: 10.5, marginTop: 8, lineHeight: 1.5 }}>
              Giá API chính thức (Anthropic docs): opus 4.5+ $5/$25 · cache-read 0.1× · cache-write 1.25×/2×.
              Bạn dùng gói subscription — đây là <b>giá nếu gọi qua API</b>, không phải tiền đã trả.
            </div>
          </div>

          {/* 3 stats */}
          <div className="grid g-3" data-testid="usage-stats">
            <div className="stat"><span className="sl">Hôm nay</span><span className="sv">{fmtTokens(u.today)}</span><span className="sd faint">tokens đốt</span></div>
            <div className="stat"><span className="sl">Trung bình/ngày</span><span className="sv">{fmtTokens(u.avgPerDay)}</span><span className="sd faint">7 ngày qua</span></div>
            <div className="stat"><span className="sl">Đỉnh</span><span className="sv">{fmtTokens(u.peak?.tokens)}</span><span className="sd faint">{u.peak?.label ?? "—"}</span></div>
          </div>
        </div>
      </div>

      {/* ---- 3. Daily-burn chart (full width) ---- */}
      <div className="card" style={{ minHeight: 180 }} data-testid="usage-daily">
        <div className="phead" style={{ padding: 0, border: 0, marginBottom: 6 }}>
          <span className="kicker">Token đốt theo ngày (7 ngày)</span>
          {u.peak?.tokens > 0 && <span className="hint" style={{ marginLeft: "auto" }}>đỉnh {fmtTokens(u.peak.tokens)} · {u.peak.label}</span>}
        </div>
        {u.series.length === 0 && <span className="hint" style={{ padding: "18px 4px" }}>Chưa có dữ liệu theo ngày.</span>}
        <div style={{ display: "flex", alignItems: "flex-end", gap: 16, flex: 1, padding: "16px 4px 0", minHeight: 130 }}>
          {u.series.map((d) => {
            const h = d.tokens > 0 ? Math.max(3, (d.tokens / maxBurn) * 120) : 3;
            const hot = d.tokens / maxBurn > 0.65;
            return (
              <div key={d.date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, justifyContent: "flex-end", height: "100%" }}>
                <span className="num faint" style={{ fontSize: 9.5 }}>{d.tokens > 0 ? fmtTokens(d.tokens) : ""}</span>
                <div style={{ width: "100%", maxWidth: 52, height: h, background: d.tokens === 0 ? "var(--bg-3)" : hot ? "var(--accent)" : "var(--accent-dim)", borderRadius: "5px 5px 0 0", boxShadow: hot ? "0 0 14px -3px var(--accent)" : undefined, transition: "height .3s ease" }} title={`${d.label}: ${fmtTokens(d.tokens)}`} />
                <span className="num faint" style={{ fontSize: 10 }}>{d.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- 4 + 5. By-model & by-project side by side ---- */}
      <div className="grid g-2" style={{ alignItems: "start" }}>
        {/* By-model */}
        <div className="panel" data-testid="usage-bymodel">
          <div className="phead">
            <span className="kicker">Theo model</span>
            <span className="hint" style={{ marginLeft: "auto" }}>{u.byModel.length} model</span>
          </div>
          <div style={{ padding: "6px 16px 12px" }}>
            {u.byModel.length > 0 ? (
              u.byModel.map((m, i) => {
                const share = Math.round((m.total / totalModelTokens) * 100);
                return (
                  <div key={m.model} style={{ padding: "8px 0", borderBottom: i < u.byModel.length - 1 ? "1px solid color-mix(in oklch, var(--line) 55%, transparent)" : "none" }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6, fontFamily: "var(--mono)", fontSize: 12 }}>
                      <i style={{ width: 9, height: 9, borderRadius: 2, background: MODEL_COLORS[i % MODEL_COLORS.length], flexShrink: 0 }} />
                      <span style={{ color: "var(--tx-0)", fontWeight: 600 }}>{modelLabel(m.model)}</span>
                      <span className="faint" style={{ marginLeft: "auto" }}>{share}%</span>
                      <span style={{ width: 64, textAlign: "right", color: "var(--tx-1)" }}>{fmtTokens(m.total)}</span>
                      <span className="acc" style={{ width: 64, textAlign: "right", fontWeight: 600 }}>{fmtUSD(m.costUSD)}</span>
                    </div>
                    <div className="bar"><i style={{ width: `${(m.total / maxModel) * 100}%`, background: MODEL_COLORS[i % MODEL_COLORS.length] }} /></div>
                  </div>
                );
              })
            ) : (
              <span className="hint">Chưa có dữ liệu model.</span>
            )}
          </div>
        </div>

        {/* By-project */}
        <div className="panel" data-testid="usage-byproject">
          <div className="phead">
            <span className="kicker">Theo dự án</span>
            {u.byProject.length > 0 && (
              <span className="hint" style={{ marginLeft: "auto" }}>top {u.byProject.length}</span>
            )}
          </div>
          <div style={{ padding: "6px 16px 12px" }}>
            {u.byProject.length > 0 ? (
              u.byProject.map((p, i) => {
                const share = Math.round((p.total / totalProjectTokens) * 100);
                return (
                  <div key={p.project} style={{ padding: "8px 0", borderBottom: i < u.byProject.length - 1 ? "1px solid color-mix(in oklch, var(--line) 55%, transparent)" : "none" }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6, fontFamily: "var(--mono)", fontSize: 12 }}>
                      <span style={{ color: "var(--tx-0)", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 130 }} title={`${p.project} · ${p.msgs} tin nhắn`}>{p.project}</span>
                      <span className="faint" style={{ marginLeft: "auto" }}>{share}%</span>
                      <span style={{ width: 60, textAlign: "right", color: "var(--tx-1)" }}>{fmtTokens(p.total)}</span>
                      <span className="acc" style={{ width: 64, textAlign: "right", fontWeight: 600 }}>{fmtUSD(p.costUSD)}</span>
                    </div>
                    <div className="bar"><i style={{ width: `${(p.total / maxProject) * 100}%`, background: MODEL_COLORS[i % MODEL_COLORS.length] }} /></div>
                  </div>
                );
              })
            ) : (
              <span className="hint" data-testid="usage-byproject-empty">
                Chưa có transcript — cần ~/.claude/projects (mounted). Token nguồn: {u.tokenSource}.
              </span>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
