"use client";
/* ============================================================
   Decision Journal + Calibration · /decision-journal (F1-H1, the FE for W7-A2).
   The general decision learning-loop (NOT the trade journal S7): log a decision +
   thesis + falsification condition + confidence% (the probability claim) → on
   resolve, an outcome (right/wrong on the THESIS axis) drives calibration.

   Stats are BACKEND-computed (Brier + confidence bands + rule-based domain bias) —
   the FE RENDERS them, never recomputes (single source of truth). Brier lower=better;
   null until ≥1 resolved. Bias flags = domains whose wrong-rate exceeds a threshold
   over a min sample (min-n gated — honest, no false-positive on sparse data).
   States: loading · error · empty · data. Writes fail-closed (422 surfaces in form).
   ============================================================ */
import { useState } from "react";
import { useDecisionJournal } from "@/lib/useDecisionJournal";
import { KpiCard, DataTable, type Column } from "@/components/shared";
import { Field, TextInput, NumberInput, Select } from "@/components/shared/Field";
import { ApiError } from "@/lib/api";
import type { DecisionEntry, DecisionOutcome } from "@/lib/types";

type CreateForm = {
  decision: string; domain: string; confidence: string; predicted: string;
  thesis: string; falsificationCondition: string; date: string;
  // EV/worst-case core (RL-reward / anti-resulting) — capture the EV thesis + accepted
  // downside + the W at decision time so a later resolve can separate skill from luck.
  expectedEv: string; worstCase: string; decisionWeight: string;
};
const EMPTY_CREATE: CreateForm = {
  decision: "", domain: "", confidence: "", predicted: "", thesis: "", falsificationCondition: "", date: "",
  expectedEv: "", worstCase: "", decisionWeight: "",
};

export default function DecisionJournalPage() {
  const { data, status, errMsg, reload, create, update, remove } = useDecisionJournal();

  const [form, setForm] = useState<CreateForm>(EMPTY_CREATE);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  async function onCreate() {
    setFormErr("");
    if (!form.decision.trim()) { setFormErr("Cần mô tả quyết định."); return; }
    if (!form.domain.trim()) { setFormErr("Cần domain (vd: investment, project)."); return; }
    const conf = Number(form.confidence);
    if (form.confidence.trim() === "" || Number.isNaN(conf) || conf < 0 || conf > 100) {
      setFormErr("Confidence là số 0–100 (xác suất bạn tin quyết định đúng)."); return;
    }
    // predicted is optional (0-1 explicit prob; else backend derives confidence/100).
    let predicted: number | null = null;
    if (form.predicted.trim() !== "") {
      predicted = Number(form.predicted);
      if (Number.isNaN(predicted) || predicted < 0 || predicted > 1) {
        setFormErr("Predicted (tùy chọn) là xác suất 0–1."); return;
      }
    }
    // decisionWeight is optional (the W from /decision cockpit, 0-1).
    let decisionWeight: number | null = null;
    if (form.decisionWeight.trim() !== "") {
      decisionWeight = Number(form.decisionWeight);
      if (Number.isNaN(decisionWeight) || decisionWeight < 0 || decisionWeight > 1) {
        setFormErr("Decision weight W (tùy chọn) là số 0–1 (dán từ Decision cockpit)."); return;
      }
    }
    setBusy(true);
    try {
      await create({
        decision: form.decision.trim(),
        domain: form.domain.trim(),
        confidence: conf,
        ...(predicted != null ? { predicted } : {}),
        thesis: form.thesis.trim() || null,
        falsificationCondition: form.falsificationCondition.trim() || null,
        ...(form.date.trim() ? { date: form.date.trim() } : {}),
        // EV/worst-case core — send only when filled (backend defaults None).
        ...(form.expectedEv.trim() ? { expectedEv: form.expectedEv.trim() } : {}),
        ...(form.worstCase.trim() ? { worstCase: form.worstCase.trim() } : {}),
        ...(decisionWeight != null ? { decisionWeight } : {}),
      });
      setForm(EMPTY_CREATE);
      setCreating(false);
    } catch (e) {
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onResolve(id: string, outcome: DecisionOutcome, lesson: string) {
    setFormErr("");
    setBusy(true);
    try {
      await update(id, { status: "resolved", outcome, lesson: lesson.trim() || null });
      setResolvingId(null);
    } catch (e) {
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (status === "loading") {
    return (
      <section className="view" data-screen="DJ" data-testid="dj-screen">
        <Vtitle />
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="dj-loading">Đang tải nhật ký quyết định…</div>
      </section>
    );
  }
  if (status === "error") {
    return (
      <section className="view" data-screen="DJ" data-testid="dj-screen">
        <Vtitle />
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="dj-error">
          {errMsg || "Không tải được."}
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      </section>
    );
  }

  const { entries, count, resolvedCount, brier, calibration, biasFlags } = data;

  const columns: Column<DecisionEntry>[] = [
    { key: "decision", header: "Quyết định", className: "pn", cell: (d) => (
      <div>
        <div>{d.decision}</div>
        {d.thesis && <div className="faint" style={{ fontSize: 11 }}>{d.thesis}</div>}
      </div>
    ) },
    { key: "domain", header: "Domain", cell: (d) => <span className="tagchip">{d.domain}</span> },
    { key: "conf", header: "Conf", className: "num", cell: (d) => `${d.confidence}%` },
    { key: "date", header: "Ngày", className: "faint", cell: (d) => d.date },
    { key: "outcome", header: "Kết quả", cell: (d) =>
      d.status === "open" ? (
        <button className="btn sm" type="button" onClick={() => { setResolvingId(d.id); setFormErr(""); }} data-testid={`dj-resolve-${d.id}`}>
          Resolve
        </button>
      ) : (
        <span className={d.outcome === "right" ? "pos" : "neg"} data-testid={`dj-outcome-${d.id}`}>
          {d.outcome === "right" ? "✓ đúng" : "✗ sai"}
        </span>
      ) },
    { key: "del", header: "", cell: (d) => (
      <button className="btn sm ghost" type="button" disabled={busy} onClick={() => remove(d.id).catch(() => {})} data-testid={`dj-del-${d.id}`}>✕</button>
    ) },
  ];

  return (
    <section className="view" data-screen="DJ" data-testid="dj-screen">
      <Vtitle />

      {/* calibration stats — backend-computed */}
      <div className="grid g-4" style={{ marginBottom: 14 }} data-testid="dj-stats">
        <KpiCard label="Quyết định" value={count} sub={`${resolvedCount} đã resolve`} />
        <KpiCard label="Brier score" value={brier == null ? "—" : brier.toFixed(3)} sub="thấp = hiệu chuẩn tốt" tone={brier == null ? undefined : brier <= 0.15 ? "pos" : brier >= 0.3 ? "neg" : undefined} />
        <KpiCard label="Bands" value={calibration.length} sub="dải confidence có dữ liệu" />
        <KpiCard label="Bias flags" value={biasFlags.length} sub="domain hay sai" tone={biasFlags.length ? "neg" : undefined} />
      </div>

      {/* bias flags (rule-based, min-n gated) */}
      {biasFlags.length > 0 && (
        <div className="panel" style={{ marginBottom: 14, padding: "12px 16px" }} data-testid="dj-bias">
          <div className="kicker" style={{ marginBottom: 8 }}>⚠ Bias — domain hay sai (rule-based, min-n)</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {biasFlags.map((b) => (
              <span key={b.domain} className="wstatus" style={{ color: "var(--red)", background: "var(--red-dim)" }} data-testid="dj-bias-flag">
                {b.domain}: sai {(b.wrongRate * 100).toFixed(0)}% (n={b.n})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* calibration bands: predicted vs actual */}
      {calibration.length > 0 && (
        <div className="panel" style={{ marginBottom: 14, padding: "12px 16px" }} data-testid="dj-calibration">
          <div className="kicker" style={{ marginBottom: 10 }}>Hiệu chuẩn — tin (predicted) vs thực tế đúng (actual), trục THESIS</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {calibration.map((c) => (
              <div key={c.band} className="wfilter-row" data-testid="dj-band">
                <span className="mut" style={{ width: 70 }}>{c.band}%</span>
                <div className="bar" style={{ flex: 1, height: 8, position: "relative" }}>
                  <i style={{ width: `${c.actual}%`, background: "var(--green)" }} />
                  {/* predicted marker */}
                  <span style={{ position: "absolute", left: `${c.predicted}%`, top: -3, width: 2, height: 14, background: "var(--accent)" }} title={`predicted ${c.predicted}%`} />
                </div>
                <span className="num" style={{ width: 90, textAlign: "right" }}>
                  {c.actual.toFixed(0)}% đúng · n={c.n}
                </span>
              </div>
            ))}
          </div>
          <div className="hint" style={{ marginTop: 8 }}>Vạch cam = mức tin trung bình của dải; cột xanh = tỉ lệ thực tế đúng. Trùng nhau = hiệu chuẩn tốt.</div>
        </div>
      )}

      {/* create */}
      <div className="panel" style={{ marginBottom: 14 }} data-testid="dj-create-panel">
        <div className="phead">
          <span className="kicker">Ghi quyết định</span>
          <button className="btn sm accent" type="button" style={{ marginLeft: "auto" }} onClick={() => { setCreating((v) => !v); setFormErr(""); }} data-testid="dj-toggle-create">
            {creating ? "Đóng" : "+ Quyết định mới"}
          </button>
        </div>
        {creating && (
          <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
            <Field label="Quyết định" testId="dj-f-decision">
              <TextInput value={form.decision} onChange={(v) => setForm({ ...form, decision: v })} placeholder="Tôi quyết định…" maxLength={2000} testId="dj-decision" />
            </Field>
            <div style={{ display: "flex", gap: 10 }}>
              <Field label="Domain" testId="dj-f-domain">
                <TextInput value={form.domain} onChange={(v) => setForm({ ...form, domain: v })} placeholder="investment / project / …" maxLength={200} testId="dj-domain" />
              </Field>
              <Field label="Confidence % (xác suất đúng)" testId="dj-f-conf">
                <NumberInput value={form.confidence === "" ? "" : Number(form.confidence)} onChange={(v) => setForm({ ...form, confidence: v === "" ? "" : String(v) })} min={0} max={100} testId="dj-confidence" />
              </Field>
              <Field label="Predicted 0–1 (tùy chọn)" testId="dj-f-predicted">
                <TextInput value={form.predicted} onChange={(v) => setForm({ ...form, predicted: v })} placeholder="vd 0.85 — bỏ trống = dùng confidence" maxLength={8} testId="dj-predicted" />
              </Field>
              <Field label="Ngày (tùy chọn)" testId="dj-f-date">
                <TextInput value={form.date} onChange={(v) => setForm({ ...form, date: v })} placeholder="2026-06-15" maxLength={32} testId="dj-date" />
              </Field>
            </div>
            <Field label="Thesis (vì sao)" testId="dj-f-thesis">
              <TextInput value={form.thesis} onChange={(v) => setForm({ ...form, thesis: v })} placeholder="Luận điểm…" maxLength={4000} testId="dj-thesis" />
            </Field>
            <Field label="Falsification — điều gì chứng minh tôi SAI" testId="dj-f-fals">
              <TextInput value={form.falsificationCondition} onChange={(v) => setForm({ ...form, falsificationCondition: v })} placeholder="Nếu X xảy ra thì thesis sai…" maxLength={4000} testId="dj-falsification" />
            </Field>
            {/* EV / worst-case core (anti-resulting) — capture the EV thesis + accepted
                downside + the W AT decision time → later separate skill from luck. All optional. */}
            <div style={{ display: "flex", gap: 10 }}>
              <Field label="Expected EV (tùy chọn)" testId="dj-f-ev">
                <TextInput value={form.expectedEv} onChange={(v) => setForm({ ...form, expectedEv: v })} placeholder='vd "positive_asymmetric"' maxLength={2000} testId="dj-expectedEv" />
              </Field>
              <Field label="Worst case chấp nhận (tùy chọn)" testId="dj-f-worst">
                <TextInput value={form.worstCase} onChange={(v) => setForm({ ...form, worstCase: v })} placeholder="downside tệ nhất tôi chấp nhận…" maxLength={2000} testId="dj-worstCase" />
              </Field>
              <Field label="Decision weight W 0–1 (tùy chọn)" testId="dj-f-w">
                <TextInput value={form.decisionWeight} onChange={(v) => setForm({ ...form, decisionWeight: v })} placeholder="dán W từ Decision cockpit" maxLength={8} testId="dj-decisionWeight" />
              </Field>
            </div>
            {formErr && <div className="hint neg" data-testid="dj-form-error">⚠ {formErr}</div>}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button className="btn accent" type="button" onClick={onCreate} disabled={busy} data-testid="dj-create-submit">
                {busy ? "Đang lưu…" : "Lưu quyết định"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* resolve panel (inline, one at a time) */}
      {resolvingId && (
        <ResolvePanel
          id={resolvingId}
          busy={busy}
          err={formErr}
          onCancel={() => { setResolvingId(null); setFormErr(""); }}
          onResolve={onResolve}
        />
      )}

      {/* list */}
      <div className="panel" data-testid="dj-list">
        <div className="phead"><span className="kicker">Quyết định · mới nhất</span></div>
        <DataTable
          columns={columns}
          rows={entries}
          rowKey={(d) => d.id}
          emptyLabel="Chưa có quyết định nào — ghi một quyết định + dự đoán confidence; khi biết kết quả, resolve để đo hiệu chuẩn."
        />
      </div>
    </section>
  );
}

function ResolvePanel({
  id, busy, err, onCancel, onResolve,
}: {
  id: string; busy: boolean; err: string;
  onCancel: () => void;
  onResolve: (id: string, outcome: DecisionOutcome, lesson: string) => void;
}) {
  const [outcome, setOutcome] = useState<DecisionOutcome>("right");
  const [lesson, setLesson] = useState("");
  return (
    <div className="panel" style={{ marginBottom: 14, borderColor: "var(--accent)" }} data-testid="dj-resolve-panel">
      <div className="phead">
        <span className="kicker">Resolve quyết định</span>
        <button className="btn sm ghost" type="button" style={{ marginLeft: "auto" }} onClick={onCancel}>Hủy</button>
      </div>
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
        <Field label="Kết quả (trục THESIS — đúng/sai luận điểm, KHÔNG phải lãi/lỗ)" testId="dj-f-outcome">
          <Select
            value={outcome}
            onChange={(v) => setOutcome(v as DecisionOutcome)}
            options={[{ value: "right", label: "✓ thesis đúng" }, { value: "wrong", label: "✗ thesis sai" }]}
            testId="dj-resolve-outcome"
          />
        </Field>
        <Field label="Bài học (tùy chọn)" testId="dj-f-lesson">
          <TextInput value={lesson} onChange={setLesson} placeholder="Rút ra điều gì…" maxLength={4000} testId="dj-resolve-lesson" />
        </Field>
        {err && <div className="hint neg" data-testid="dj-resolve-error">⚠ {err}</div>}
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button className="btn accent" type="button" onClick={() => onResolve(id, outcome, lesson)} disabled={busy} data-testid="dj-resolve-submit">
            {busy ? "Đang lưu…" : "Resolve"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Vtitle() {
  return (
    <div className="vtitle">
      <h1>Nhật ký quyết định</h1>
      <span className="sub">decision · thesis · confidence → resolve → hiệu chuẩn (Brier · bands · bias)</span>
    </div>
  );
}
