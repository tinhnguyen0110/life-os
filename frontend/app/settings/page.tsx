"use client";
/* ============================================================
   S12 — Settings hub. Ported from mock screens-system.js SCREENS.settings.
   The FIRST write/forms screen. 4 areas:
   (a) Automation toàn cục — global-config forms → PATCH /settings (briefHour /
       idleThresholdDays number fields w/ Lưu + per-field 422 echo; master + pattern
       toggles save-on-flip, FAIL-CLOSED refetch).
   (b) Tài khoản — displayName / timezone text fields + errorChannel select → PATCH.
   (c) Tích hợp & MCP — HONEST STATUS panel (live / phase-2 badges, NOT fake toggles).
   (d) API endpoints — live-status list.
   (e) link-outs to registry CRUD (projects→/projects, finance→/finance — NOT rebuilt).
   (f) Mở Tweaks — honest coming-soon (no theme system this build).
   render-only on reads; NO optimistic writes (mutate→await→refetch).
   ============================================================ */
import { useEffect, useState } from "react";
import { useSettings } from "@/lib/useSettings";
import { useSafeRouter } from "@/lib/useNav";
import { Field, TextInput, NumberInput, Select, Toggle } from "@/components/shared/Field";
import { apiBase } from "@/lib/api";
import type { AppConfig, AppConfigPatch } from "@/lib/types";

const ERROR_CHANNELS = [
  { value: "inapp", label: "Trong ứng dụng" },
  { value: "discord", label: "Discord" },
  { value: "none", label: "Tắt (không báo)" },
];

/** Integration status — HONEST: live (wired) vs phase-2 (not built). NO fake toggles. */
const INTEGRATIONS: { name: string; desc: string; status: "live" | "phase2" }[] = [
  { name: "Claude Code (MCP)", desc: "AI đọc data + kích hoạt routine — phase 2 (ARCH §11)", status: "phase2" },
  { name: "GitHub", desc: "Đọc commit/branch của repo đã đăng ký (read-only)", status: "live" },
  { name: "Market data feed", desc: "Crypto + chứng khoán qua routine market-poll", status: "live" },
  { name: "Webhook", desc: "Nhận event commit/giá từ ngoài — phase 2", status: "phase2" },
];

const API_ENDPOINTS = ["GET /settings", "PATCH /settings", "GET /routines", "POST /routines/{id}/run", "GET /activity", "GET /brief"];

export default function SettingsPage() {
  const { config, status, errMsg, reload, save } = useSettings();
  const router = useSafeRouter();

  if (status === "loading") {
    return (
      <section className="view" data-screen="S12" data-testid="settings-screen">
        <Vtitle />
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="settings-loading">Đang tải cài đặt…</div>
      </section>
    );
  }
  if (status === "error" || !config) {
    return (
      <section className="view" data-screen="S12" data-testid="settings-screen">
        <Vtitle />
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="settings-error">
          Không tải được cài đặt: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      </section>
    );
  }

  return (
    <section className="view" data-screen="S12" data-testid="settings-screen">
      <Vtitle />
      <div className="grid g-2" style={{ alignItems: "start" }}>
        {/* LEFT column: automation config + account */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <AutomationPanel config={config} save={save} />
          <AccountPanel config={config} save={save} router={router} />
        </div>
        {/* RIGHT column: integrations (honest status) + API status + appearance */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <IntegrationsPanel />
          <ApiStatusPanel />
          <AppearancePanel />
        </div>
      </div>
    </section>
  );
}

function Vtitle() {
  return (
    <div className="vtitle">
      <h1>Cài đặt</h1>
      <span className="sub">tài khoản · automation · tích hợp</span>
    </div>
  );
}

type SaveFn = ReturnType<typeof useSettings>["save"];

/** A single number-config row: local draft + Lưu button + per-field 422 echo. */
function NumberConfigRow({
  label, desc, name, value, min, max, suffix, save,
}: { label: string; desc: string; name: keyof AppConfig; value: number; min?: number; max?: number; suffix?: string; save: SaveFn }) {
  const [draft, setDraft] = useState<number | "">(value);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [savedOk, setSavedOk] = useState(false);

  useEffect(() => { setDraft(value); }, [value]);
  const dirty = draft !== "" && draft !== value;

  async function onSave() {
    if (draft === "") { setErr("không được để trống"); return; }
    setBusy(true); setErr(null); setSavedOk(false);
    const res = await save({ [name]: draft } as AppConfigPatch);
    setBusy(false);
    if (res.ok) { setSavedOk(true); }
    else { setErr(res.fieldErrors?.[name] ?? res.formError ?? "lưu thất bại"); }
  }

  return (
    <div className="set-row">
      <div className="sr-info">
        <div className="sr-t">{label}</div>
        <div className="sr-d">{desc}</div>
      </div>
      <Field label="" error={err} testId={`cfg-${name}`}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 80 }}>
            <NumberInput value={draft} onChange={(v) => { setDraft(v); setSavedOk(false); }} min={min} max={max} invalid={!!err} testId={`cfg-${name}-input`} />
          </div>
          {suffix && <span className="hint">{suffix}</span>}
          <button className="btn sm accent" type="button" disabled={busy || !dirty} onClick={onSave} data-testid={`cfg-${name}-save`}>
            {busy ? "…" : savedOk && !dirty ? "✓" : "Lưu"}
          </button>
        </div>
      </Field>
    </div>
  );
}

/** A toggle row that saves on flip (fail-closed: await→refetch via save()). */
function ToggleRow({ label, desc, name, value, save }: { label: string; desc: string; name: keyof AppConfig; value: boolean; save: SaveFn }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onFlip(next: boolean) {
    setBusy(true); setErr(null);
    const res = await save({ [name]: next } as AppConfigPatch);
    setBusy(false);
    if (!res.ok) setErr(res.fieldErrors?.[name] ?? res.formError ?? "lưu thất bại");
  }

  return (
    <div className="set-row">
      <div className="sr-info">
        <div className="sr-t">{label}</div>
        <div className="sr-d">{err ? <span className="neg">⚠ {err}</span> : desc}</div>
      </div>
      <Toggle on={value} onChange={onFlip} disabled={busy} label={label} testId={`cfg-${name}-toggle`} />
    </div>
  );
}

function AutomationPanel({ config, save }: { config: AppConfig; save: SaveFn }) {
  return (
    <div>
      <div className="kicker" style={{ marginBottom: 10 }}>Automation toàn cục</div>
      <div className="set-group" data-testid="settings-automation">
        <ToggleRow label="Master automation" desc="Bật/tắt toàn bộ routine cùng lúc" name="automationEnabled" value={config.automationEnabled} save={save} />
        <NumberConfigRow label="Giờ chạy brief" desc="Morning brief mỗi ngày lúc (giờ UTC 0–23)" name="briefHour" value={config.briefHour} min={0} max={23} suffix="giờ" save={save} />
        <NumberConfigRow label="Ngưỡng idle hunter" desc="Cảnh báo dự án đứng quá N ngày (≥1)" name="idleThresholdDays" value={config.idleThresholdDays} min={1} suffix="ngày" save={save} />
        <ToggleRow label="Pattern check" desc="Routine build-to-90 (phát hiện dự án 90% rồi bỏ)" name="patternCheckEnabled" value={config.patternCheckEnabled} save={save} />
      </div>
    </div>
  );
}

function AccountPanel({ config, save, router }: { config: AppConfig; save: SaveFn; router: ReturnType<typeof useSafeRouter> }) {
  const [name, setName] = useState(config.displayName);
  const [tz, setTz] = useState(config.timezone);
  const [chan, setChan] = useState(config.errorChannel);
  const [nameErr, setNameErr] = useState<string | null>(null);
  const [tzErr, setTzErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => { setName(config.displayName); setTz(config.timezone); setChan(config.errorChannel); }, [config]);

  async function saveField(field: "displayName" | "timezone" | "errorChannel", value: string, setErr: (e: string | null) => void) {
    setBusy(field); setErr(null);
    const res = await save({ [field]: value } as AppConfigPatch);
    setBusy(null);
    if (!res.ok) setErr(res.fieldErrors?.[field] ?? res.formError ?? "lưu thất bại");
  }

  return (
    <div>
      <div className="kicker" style={{ marginBottom: 10 }}>Tài khoản</div>
      <div className="set-group" data-testid="settings-account">
        <div className="set-row">
          <div className="sr-info" style={{ maxWidth: 240 }}>
            <Field label="Tên hiển thị" htmlFor="cfg-displayName" error={nameErr} hint="có thể để trống" testId="cfg-displayName">
              <TextInput id="cfg-displayName" value={name} onChange={(v) => { setName(v); setNameErr(null); }} maxLength={80} placeholder="Tên của bạn" invalid={!!nameErr} testId="cfg-displayName-input" />
            </Field>
          </div>
          <button className="btn sm accent" type="button" disabled={busy === "displayName" || name === config.displayName} onClick={() => saveField("displayName", name, setNameErr)} data-testid="cfg-displayName-save">
            {busy === "displayName" ? "…" : "Lưu"}
          </button>
        </div>
        <div className="set-row">
          <div className="sr-info" style={{ maxWidth: 240 }}>
            <Field label="Múi giờ" htmlFor="cfg-timezone" error={tzErr} hint="nhãn hiển thị (lưu-only)" testId="cfg-timezone">
              <TextInput id="cfg-timezone" value={tz} onChange={(v) => { setTz(v); setTzErr(null); }} maxLength={64} placeholder="Asia/Ho_Chi_Minh" invalid={!!tzErr} testId="cfg-timezone-input" />
            </Field>
          </div>
          <button className="btn sm accent" type="button" disabled={busy === "timezone" || tz === config.timezone} onClick={() => saveField("timezone", tz, setTzErr)} data-testid="cfg-timezone-save">
            {busy === "timezone" ? "…" : "Lưu"}
          </button>
        </div>
        <div className="set-row">
          <div className="sr-info" style={{ maxWidth: 240 }}>
            <Field label="Kênh báo lỗi" htmlFor="cfg-errorChannel" hint="khi routine lỗi, báo qua đâu" testId="cfg-errorChannel">
              <Select id="cfg-errorChannel" value={chan} onChange={(v) => { setChan(v as AppConfig["errorChannel"]); saveField("errorChannel", v, () => {}); }} options={ERROR_CHANNELS} disabled={busy === "errorChannel"} testId="cfg-errorChannel-input" />
            </Field>
          </div>
        </div>
        {/* link-out to project registry CRUD (NOT rebuilt here) */}
        <div className="set-row">
          <div className="sr-info"><div className="sr-t">Quản lý dự án</div><div className="sr-d">Thêm/sửa pointer repo trong màn Dự án</div></div>
          <button className="btn sm" type="button" onClick={() => router.push("/projects")} data-testid="link-projects">Mở Dự án →</button>
        </div>
        <div className="set-row">
          <div className="sr-info"><div className="sr-t">Quản lý kênh đầu tư</div><div className="sr-d">Phân bổ / mục tiêu trong màn Tài chính</div></div>
          <button className="btn sm" type="button" onClick={() => router.push("/finance")} data-testid="link-finance">Mở Tài chính →</button>
        </div>
      </div>
    </div>
  );
}

function IntegrationsPanel() {
  return (
    <div>
      <div className="kicker" style={{ marginBottom: 10 }}>Tích hợp & MCP</div>
      <div className="set-group" data-testid="settings-integrations">
        {INTEGRATIONS.map((it) => (
          <div className="set-row" key={it.name} data-testid={`integration-${it.status}`}>
            <div className="sr-info"><div className="sr-t">{it.name}</div><div className="sr-d">{it.desc}</div></div>
            {/* HONEST STATUS — live (green) / phase-2 (amber). NO fake toggle. */}
            <span className={`sbadge ${it.status === "live" ? "sb-act" : "sb-slow"}`}>
              {it.status === "live" ? "live" : "phase 2"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ApiStatusPanel() {
  return (
    <div>
      <div className="kicker" style={{ marginBottom: 10 }}>API endpoints</div>
      <div className="set-group" data-testid="settings-api">
        {API_ENDPOINTS.map((e) => (
          <div className="set-row" key={e}>
            <span className="num" style={{ fontSize: 12, color: "var(--tx-1)", flex: 1, fontFamily: "var(--mono)" }}>{e}</span>
            <span className="sbadge sb-act">live</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AppearancePanel() {
  return (
    <div>
      <div className="kicker" style={{ marginBottom: 10 }}>Giao diện</div>
      <div className="set-group" data-testid="settings-appearance">
        <div className="set-row">
          <div className="sr-info">
            <div className="sr-t">Tweaks (màu / nền / hiệu ứng)</div>
            {/* HONEST: no theme/Tweaks system this build → coming-soon, not a fake button. */}
            <div className="sr-d">Panel tuỳ biến giao diện — sắp có</div>
          </div>
          <button className="btn sm" type="button" disabled title="Sắp có" data-testid="open-tweaks">Mở Tweaks</button>
        </div>
      </div>
    </div>
  );
}
