"use client";
/* ============================================================
   S7 — Nhật ký lệnh (Journal). Ported from mock screens-finance.js SCREENS.journal
   + SPEC §S7 decision fields. Tabs filter · 4 stat cards · trade-log table ·
   "Ghi lệnh" create form (execution + decision: thesis/negation/confidence/channel)
   · close-entry (outcome/pnl/lesson via PUT) · calibration panel.
   RENDER-ONLY stats (backend-computed; null → "—"). Writes FAIL-CLOSED.
   ============================================================ */
import { useMemo, useState } from "react";
import { useJournal } from "@/lib/useJournal";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { fmtMonthYear, fmtPct, orDash } from "@/lib/format";
import { apiBase, ApiError } from "@/lib/api";
import type { JournalEntry, JournalInput, JournalChannel } from "@/lib/types";

type Filter = "all" | "BUY" | "SELL" | "ladder";
type CreateForm = { action: "BUY" | "SELL"; asset: string; size: string; px: string; tag: string; reason: string; channel: JournalChannel | "none"; thesis: string; negationCondition: string; confidence: string };
type CloseForm = { pnl: string; outcome: "right" | "wrong"; lesson: string };

const EMPTY_CREATE: CreateForm = { action: "BUY", asset: "", size: "", px: "", tag: "", reason: "", channel: "none", thesis: "", negationCondition: "", confidence: "" };

const TABS: { key: Filter; label: string }[] = [
  { key: "all", label: "Tất cả" }, { key: "BUY", label: "Mua" }, { key: "SELL", label: "Bán" }, { key: "ladder", label: "Ladder" },
];

/** stat value or "—" for null (render-only; never fabricate). */
const statPct = (v: number | null) => (v == null ? "—" : `${v.toFixed(0)}%`);

export default function JournalPage() {
  const { data, status, errMsg, warning, reload, create, close } = useJournal();
  const [filter, setFilter] = useState<Filter>("all");
  const [creating, setCreating] = useState<CreateForm | null>(null);
  const [closingId, setClosingId] = useState<string | null>(null);
  const [closeForm, setCloseForm] = useState<CloseForm>({ pnl: "", outcome: "right", lesson: "" });
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");

  const entries = data.entries ?? [];
  const filtered = useMemo(() => {
    if (filter === "all") return entries;
    if (filter === "ladder") return entries.filter((e) => e.tag === "ladder");
    return entries.filter((e) => e.action === filter);
  }, [entries, filter]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!creating) return;
    setFormErr("");
    if (!creating.asset.trim() || !creating.reason.trim()) {
      setFormErr("Cần tài sản + lý do quyết định.");
      return;
    }
    const conf = creating.confidence.trim() === "" ? null : Number(creating.confidence);
    if (conf != null && (!Number.isFinite(conf) || conf < 0 || conf > 100)) {
      setFormErr("Confidence phải 0–100.");
      return;
    }
    const body: JournalInput = {
      action: creating.action, asset: creating.asset.trim(), size: creating.size, px: creating.px,
      tag: creating.tag, reason: creating.reason.trim(),
      channel: creating.channel === "none" ? null : creating.channel,
      thesis: creating.thesis || null, negationCondition: creating.negationCondition || null, confidence: conf,
    };
    setBusy(true);
    try {
      await create(body);
      setCreating(null);
    } catch (err) {
      setFormErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onClose(e: React.FormEvent) {
    e.preventDefault();
    if (!closingId) return;
    setFormErr("");
    if (!closeForm.pnl.trim()) {
      setFormErr("Cần nhập P&L (vd +5.5%).");
      return;
    }
    const entry = entries.find((x) => x.id === closingId);
    if (!entry) return;
    const body: JournalInput = {
      action: entry.action, asset: entry.asset, size: entry.size, px: entry.px, tag: entry.tag, reason: entry.reason,
      channel: entry.channel, thesis: entry.thesis, negationCondition: entry.negationCondition, confidence: entry.confidence,
      pnl: closeForm.pnl.trim(), outcome: closeForm.outcome, lesson: closeForm.lesson || null,
    };
    setBusy(true);
    try {
      await close(closingId, body);
      setClosingId(null);
      setCloseForm({ pnl: "", outcome: "right", lesson: "" });
    } catch (err) {
      setFormErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<JournalEntry>[] = [
    { key: "date", header: "Ngày", className: "faint", cell: (j) => fmtMonthYear(j.date) },
    { key: "action", header: "Lệnh", cell: (j) => <span className={`tradechip ${j.action.toLowerCase()}`}>{j.action}</span> },
    { key: "asset", header: "Tài sản", className: "pn", cell: (j) => j.asset },
    { key: "size", header: "Khối lượng", cell: (j) => orDash(j.size) },
    { key: "px", header: "Giá", className: "mut", cell: (j) => orDash(j.px) },
    { key: "tag", header: "Loại", cell: (j) => (j.tag ? <span className="tagchip">{j.tag}</span> : "—") },
    {
      key: "pnl", header: "P&L",
      cell: (j) => <span className={j.pnl ? (j.pnl.startsWith("-") || j.pnl.startsWith("−") ? "neg" : "pos") : "faint"}>{j.pnl ?? "mở"}</span>,
    },
    { key: "conf", header: "Conf", className: "faint", cell: (j) => (j.confidence != null ? `${j.confidence}%` : "—") },
    {
      key: "act", header: "",
      cell: (j) =>
        j.outcome === "open" ? (
          <button className="btn sm" type="button" onClick={() => { setClosingId(j.id); setFormErr(""); }} data-testid={`close-${j.id}`}>Đóng lệnh</button>
        ) : (
          <span className={j.outcome === "right" ? "pos" : "neg"}>{j.outcome === "right" ? "✓ đúng" : "✗ sai"}</span>
        ),
    },
  ];

  return (
    <section className="view" data-screen="S7" data-testid="journal-screen">
      <div className="vtitle">
        <h1>Nhật ký lệnh</h1>
        <span className="sub">{data.count} lệnh · ghi lại lý do, không chỉ con số</span>
        <span className="sp" />
        <div className="tabs">
          {TABS.map((t) => (
            <button key={t.key} type="button" className={`tab${filter === t.key ? " on" : ""}`} onClick={() => setFilter(t.key)} data-testid={`tab-${t.key}`}>{t.label}</button>
          ))}
        </div>
        <button className="btn accent" type="button" onClick={() => { setCreating({ ...EMPTY_CREATE }); setFormErr(""); }} data-testid="journal-new">+ Ghi lệnh</button>
      </div>

      {warning && <div className="panel" style={{ padding: "10px 14px" }} data-testid="journal-warning"><span className="hint mid">⚠ {warning}</span></div>}

      {/* 4 stat cards — render-only, null → "—" */}
      <div className="grid g-4" data-testid="journal-stats">
        <div className="stat"><span className="sl">Win rate</span><span className={`sv ${(data.winRate ?? 0) > 0 ? "pos" : ""}`}>{statPct(data.winRate)}</span><span className="sd faint">lệnh đã đóng</span></div>
        <div className="stat"><span className="sl">P&L trung bình</span><span className={`sv ${(data.avgPnl ?? 0) < 0 ? "neg" : "pos"}`}>{data.avgPnl != null ? fmtPct(data.avgPnl) : "—"}</span><span className="sd faint">mỗi lệnh đóng</span></div>
        {/* Honest label: this is the ladder-TAGGED ratio, NOT plan-adherence. */}
        <div className="stat"><span className="sl">Tỷ lệ ladder</span><span className="sv acc">{statPct(data.ladderDiscipline)}</span><span className="sd faint">% lệnh gắn tag "ladder"</span></div>
        <div className="stat"><span className="sl">Lệnh tháng này</span><span className="sv">{data.thisMonth.total}</span><span className="sd faint">{data.thisMonth.buy} mua · {data.thisMonth.sell} bán · {data.thisMonth.ladder} ladder</span></div>
      </div>

      {/* Create form (execution + SPEC decision fields) */}
      {creating && (
        <div className="panel" data-testid="journal-create-form">
          <div className="phead"><span className="kicker">Ghi lệnh mới</span></div>
          <form onSubmit={onCreate} style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <select className="tab" value={creating.action} onChange={(e) => setCreating({ ...creating, action: e.target.value as "BUY" | "SELL" })} data-testid="c-action"><option value="BUY">BUY</option><option value="SELL">SELL</option></select>
            <input className="tab" placeholder="Tài sản (BTC)" value={creating.asset} onChange={(e) => setCreating({ ...creating, asset: e.target.value })} data-testid="c-asset" />
            <input className="tab" placeholder="Khối lượng ($2,000)" value={creating.size} onChange={(e) => setCreating({ ...creating, size: e.target.value })} data-testid="c-size" />
            <input className="tab" placeholder="Giá ($68,240)" value={creating.px} onChange={(e) => setCreating({ ...creating, px: e.target.value })} data-testid="c-px" />
            <input className="tab" placeholder="Loại (ladder/dca/value)" value={creating.tag} onChange={(e) => setCreating({ ...creating, tag: e.target.value })} data-testid="c-tag" />
            <select className="tab" value={creating.channel} onChange={(e) => setCreating({ ...creating, channel: e.target.value as CreateForm["channel"] })} data-testid="c-channel"><option value="none">— kênh —</option><option value="crypto">crypto</option><option value="etf">etf</option><option value="vn">vn</option><option value="dry">dry</option></select>
            <input className="tab" style={{ gridColumn: "1 / 3" }} placeholder="Lý do quyết định" value={creating.reason} onChange={(e) => setCreating({ ...creating, reason: e.target.value })} data-testid="c-reason" />
            <input className="tab" style={{ gridColumn: "1 / 3" }} placeholder="Luận điểm (thesis)" value={creating.thesis} onChange={(e) => setCreating({ ...creating, thesis: e.target.value })} data-testid="c-thesis" />
            <input className="tab" placeholder="Điều kiện phủ định (negation)" value={creating.negationCondition} onChange={(e) => setCreating({ ...creating, negationCondition: e.target.value })} data-testid="c-negation" />
            <input className="tab" placeholder="Confidence 0-100" inputMode="numeric" value={creating.confidence} onChange={(e) => setCreating({ ...creating, confidence: e.target.value })} data-testid="c-confidence" />
            {formErr && <span className="hint neg" style={{ gridColumn: "1 / 3" }} data-testid="create-error">{formErr}</span>}
            <div className="row" style={{ gap: 8, gridColumn: "1 / 3" }}>
              <button className="btn accent" type="submit" disabled={busy} data-testid="c-submit">{busy ? "Đang lưu…" : "Ghi lệnh"}</button>
              <button className="btn" type="button" onClick={() => setCreating(null)} disabled={busy}>Hủy</button>
            </div>
          </form>
        </div>
      )}

      {/* Close-entry form */}
      {closingId && (
        <div className="panel" data-testid="journal-close-form">
          <div className="phead"><span className="kicker">Đóng lệnh</span></div>
          <form onSubmit={onClose} style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
            <input className="tab num" placeholder="P&L (+5.5% / -4.1%)" value={closeForm.pnl} onChange={(e) => setCloseForm({ ...closeForm, pnl: e.target.value })} data-testid="close-pnl" />
            <select className="tab" value={closeForm.outcome} onChange={(e) => setCloseForm({ ...closeForm, outcome: e.target.value as "right" | "wrong" })} data-testid="close-outcome"><option value="right">Đúng</option><option value="wrong">Sai</option></select>
            <input className="tab" placeholder="Bài học (tùy chọn)" value={closeForm.lesson} onChange={(e) => setCloseForm({ ...closeForm, lesson: e.target.value })} data-testid="close-lesson" />
            {formErr && <span className="hint neg" data-testid="close-error">{formErr}</span>}
            <div className="row" style={{ gap: 8 }}>
              <button className="btn accent" type="submit" disabled={busy} data-testid="close-submit">{busy ? "Đang đóng…" : "Đóng lệnh"}</button>
              <button className="btn" type="button" onClick={() => setClosingId(null)} disabled={busy}>Hủy</button>
            </div>
          </form>
        </div>
      )}

      {status === "loading" && <div className="hint" style={{ padding: "24px 4px" }} data-testid="journal-loading">Đang tải nhật ký…</div>}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="journal-error">
          Không tải được nhật ký: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <>
          <div className="panel" style={{ overflow: "hidden" }}>
            <div className="phead"><span className="kicker">Mọi lệnh</span><span className="hint" style={{ marginLeft: "auto" }}>mới nhất trước</span></div>
            <DataTable columns={columns} rows={filtered} rowKey={(j) => j.id} emptyLabel={filter === "all" ? "Chưa có lệnh nào." : "Không có lệnh khớp bộ lọc."} />
          </div>

          {/* Calibration panel — thesis accuracy (outcome-based), DISTINCT from
              win-rate (pnl-based): a lucky profit on a wrong thesis is a calib miss. */}
          <div className="panel" data-testid="journal-calibration">
            <div className="phead">
              <span className="kicker">Calibration · confidence vs thực tế</span>
              <span className="hint" style={{ marginLeft: "auto" }}>độ chuẩn của luận điểm (≠ win-rate theo P&amp;L)</span>
            </div>
            <div style={{ padding: "8px 16px 14px" }}>
              {data.calibration.length > 0 ? (
                <>
                  {data.calibration.map((c) => {
                    const lowN = c.n < 3; // n=1,2 = noise → gray-out + caveat
                    return (
                      <div className="usebar-row" key={c.band} style={lowN ? { opacity: 0.55 } : undefined} data-testid={`calib-${c.band}`}>
                        <span className="ul">{c.band}% (n={c.n}{lowN ? " ⚠" : ""})</span>
                        <span className="ub"><i style={{ width: `${Math.max(0, Math.min(100, c.actual))}%`, background: c.actual >= c.predicted ? "var(--green)" : "var(--amber)" }} /></span>
                        <span className="uv">thực {c.actual.toFixed(0)}%</span>
                        <span className="uv faint">dự {c.predicted.toFixed(0)}%</span>
                      </div>
                    );
                  })}
                  {data.calibration.some((c) => c.n < 3) && (
                    <span className="hint" style={{ display: "block", marginTop: 6 }} data-testid="calib-lown-note">
                      ⚠ Band n&lt;3 là nhiễu thống kê — chưa đủ mẫu để tin.
                    </span>
                  )}
                </>
              ) : (
                <span className="hint" data-testid="calib-empty">Chưa đủ dữ liệu để hiệu chỉnh (cần lệnh đã đóng + có confidence).</span>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
