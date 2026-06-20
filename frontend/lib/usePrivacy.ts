"use client";
/* ============================================================
   usePrivacy — device-local privacy-mode state (#72 + #74).
   - `privacy` (on/off) persists in localStorage["lifeos.privacy"] (device-local veil).
   - `unlocked` is a SESSION-only flag (#74 change 5): privacy ON starts LOCKED (money
     HIDDEN as ••••); a correct pass via POST /settings/privacy/verify UNLOCKS (money
     shown) until the user toggles privacy off. Toggling off resets unlocked→false, so
     toggling on again re-locks. unlocked is NOT persisted (a session reveal, not a
     standing setting) and NOT a backend field.

   The body attr `data-privacy="on"` means "HIDE money NOW" = (privacy && !unlocked). The
   [data-privacy="on"] [data-amount] CSS masks the totals (display-only — the real value
   stays in the DOM, recoverable when unlocked / toggled off, no reload). ONE mechanism,
   app-wide. Cross-instance: a write broadcasts on a CustomEvent so the TopBar button, the
   reveal modal, and the masked spans all agree in the same tab; `storage` covers tabs.

   SSR + first paint start from DEFAULT (OFF) so server/client agree; persisted value
   loads in the mount effect (hydration-safe).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { DEFAULT_PRIVACY, STORAGE_KEY, loadPrivacy, savePrivacy, normalizePrivacy } from "@/lib/privacy";
import { verifyPrivacyPass, ApiError } from "@/lib/api";

/** Same-tab broadcast channel — carries the full {privacy, unlocked} state. */
const SYNC_EVENT = "lifeos:privacy";

interface PrivacyState {
  privacy: boolean;
  unlocked: boolean;
}

/** Persist privacy (NOT unlocked — that's session-only) + broadcast the full state. */
function commit(next: PrivacyState): void {
  savePrivacy(next.privacy);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<PrivacyState>(SYNC_EVENT, { detail: next }));
  }
}

/** Reflect "hide money now" onto the body so the mask CSS applies app-wide.
 *  Hide = privacy ON AND still locked. */
function applyBodyAttr(s: PrivacyState): void {
  if (typeof document === "undefined") return;
  const hide = s.privacy && !s.unlocked;
  if (hide) document.body.setAttribute("data-privacy", "on");
  else document.body.removeAttribute("data-privacy");
}

export interface UsePrivacy {
  /** privacy mode on/off (persisted). When ON the eye shows 🙈. */
  privacy: boolean;
  /** revealed this session via the pass (only meaningful while privacy ON). */
  unlocked: boolean;
  /** true = money is currently HIDDEN (privacy ON and not yet unlocked). */
  locked: boolean;
  ready: boolean;
  /** flip privacy on/off. Turning OFF also clears unlocked (re-lock on next ON). */
  toggle: () => void;
  setPrivacy: (on: boolean) => void;
  /** submit a pass attempt → POST verify → on ok, UNLOCK. Returns {ok} (false on wrong
   *  pass or network error — the modal shows the error, stays locked). */
  unlock: (pass: string) => Promise<{ ok: boolean; error?: string }>;
}

export function usePrivacy(): UsePrivacy {
  const [state, setState] = useState<PrivacyState>({ privacy: DEFAULT_PRIVACY, unlocked: false });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const initial: PrivacyState = { privacy: loadPrivacy(), unlocked: false };
    setState(initial);
    applyBodyAttr(initial);
    setReady(true);

    function onSync(e: Event) {
      const next = (e as CustomEvent<PrivacyState>).detail;
      if (next) { setState(next); applyBodyAttr(next); }
    }
    function onStorage(e: StorageEvent) {
      if (e.key !== STORAGE_KEY) return;
      let privacy = DEFAULT_PRIVACY;
      try {
        privacy = e.newValue ? normalizePrivacy(JSON.parse(e.newValue)) : DEFAULT_PRIVACY;
      } catch {
        privacy = DEFAULT_PRIVACY;
      }
      // a cross-tab privacy change re-locks (unlocked is per-tab session state)
      const next = { privacy, unlocked: false };
      setState(next);
      applyBodyAttr(next);
    }

    window.addEventListener(SYNC_EVENT, onSync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SYNC_EVENT, onSync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const setPrivacy = useCallback((on: boolean) => {
    // turning privacy OFF clears unlocked; turning ON starts LOCKED (unlocked=false).
    const next: PrivacyState = { privacy: on, unlocked: false };
    commit(next);
    setState(next);
    applyBodyAttr(next);
  }, []);

  const toggle = useCallback(() => {
    // read the current privacy truth from the body attr's INVERSE isn't reliable (the
    // attr is the HIDE signal, not the privacy flag) — use the latest state.
    setState((cur) => {
      const next: PrivacyState = { privacy: !cur.privacy, unlocked: false };
      commit(next);
      applyBodyAttr(next);
      return next;
    });
  }, []);

  const unlock = useCallback(async (pass: string): Promise<{ ok: boolean; error?: string }> => {
    try {
      const res = await verifyPrivacyPass(pass);
      if (res?.data?.ok) {
        setState((cur) => {
          const next = { ...cur, unlocked: true };
          // unlocked is session-only: broadcast (so all instances reveal) but do NOT
          // change the persisted privacy flag (commit still saves privacy=current).
          commit(next);
          applyBodyAttr(next);
          return next;
        });
        return { ok: true };
      }
      return { ok: false, error: "Sai mã" };
    } catch (e) {
      return { ok: false, error: e instanceof ApiError ? e.message : (e as Error).message };
    }
  }, []);

  const locked = state.privacy && !state.unlocked;
  return { privacy: state.privacy, unlocked: state.unlocked, locked, ready, toggle, setPrivacy, unlock };
}
