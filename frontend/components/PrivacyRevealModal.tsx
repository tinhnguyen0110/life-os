"use client";
/* ============================================================
   PrivacyRevealModal — #74 change 5. When privacy is ON + LOCKED (money hidden as ••••),
   this modal collects a pass and submits it via usePrivacy().unlock → POST
   /settings/privacy/verify. On ok → unlock (money shows until toggle-off). On wrong pass
   → "Sai mã" error, stays locked. The pass lives in BE env; the FE only sends the attempt.
   ============================================================ */
import { useEffect, useRef, useState } from "react";

export function PrivacyRevealModal({
  open,
  onClose,
  onSubmit,
  onTurnOff,
}: {
  open: boolean;
  onClose: () => void;
  /** returns {ok, error} — the modal shows the error + stays open on failure. */
  onSubmit: (pass: string) => Promise<{ ok: boolean; error?: string }>;
  /** turn privacy fully OFF (money normal, un-armed) — no pass needed (the user already
   *  chose to disable the veil). Optional; when given, a "Tắt riêng tư" link shows. */
  onTurnOff?: () => void;
}) {
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // reset + focus when opened
  useEffect(() => {
    if (open) {
      setPass("");
      setErr(null);
      setBusy(false);
      // focus after paint
      const t = setTimeout(() => inputRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
  }, [open]);

  if (!open) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    const res = await onSubmit(pass);
    setBusy(false);
    if (res.ok) {
      onClose(); // unlocked → close
    } else {
      setErr(res.error ?? "Sai mã");
      setPass("");
      inputRef.current?.focus();
    }
  }

  return (
    <>
      <div className="pv-backdrop" onClick={onClose} data-testid="privacy-modal-backdrop" />
      <div className="pv-modal" role="dialog" aria-modal="true" aria-label="Mở khóa số tiền" data-testid="privacy-modal">
        <div className="pv-modal-head">
          <span aria-hidden style={{ fontSize: 15 }}>🔒</span>
          <b>Mở khóa số tiền</b>
          <button type="button" className="pv-modal-x" onClick={onClose} aria-label="Đóng" data-testid="privacy-modal-close">✕</button>
        </div>
        <form onSubmit={submit} className="pv-modal-body">
          <label className="hint" htmlFor="pv-pass" style={{ fontSize: 11.5 }}>Nhập mã để hiện số tiền</label>
          <input
            ref={inputRef}
            id="pv-pass"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            className="finput"
            value={pass}
            onChange={(e) => { setPass(e.target.value); setErr(null); }}
            placeholder="••••"
            disabled={busy}
            data-testid="privacy-modal-input"
          />
          {err && <div className="hint neg" style={{ fontSize: 11.5 }} data-testid="privacy-modal-error">⚠ {err}</div>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
            <button type="button" className="btn ghost" onClick={onClose} disabled={busy} data-testid="privacy-modal-cancel">Hủy</button>
            <button type="submit" className="btn accent" disabled={busy || pass === ""} data-testid="privacy-modal-submit">
              {busy ? "Đang kiểm tra…" : "Mở khóa"}
            </button>
          </div>
          {onTurnOff && (
            <button
              type="button"
              className="hint"
              onClick={onTurnOff}
              disabled={busy}
              style={{ background: "none", border: 0, cursor: "pointer", color: "var(--tx-2)", fontSize: 11, textDecoration: "underline", alignSelf: "center", marginTop: 2 }}
              data-testid="privacy-modal-turnoff"
            >
              Tắt chế độ riêng tư (hiện số tiền)
            </button>
          )}
        </form>
      </div>
    </>
  );
}

export default PrivacyRevealModal;
