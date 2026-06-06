"use client";
/* ============================================================
   useSettings — S12 global AppConfig (read + partial write). FAIL-CLOSED writes:
   save() does PATCH → on success replaces the config from the SERVER response (no
   optimistic mutation); on 422 surfaces per-field errors (ApiError.fieldErrors()).
   Types mirror frozen settings/schema.py. Malformed-body guard on read.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getSettings, patchSettings, ApiError } from "@/lib/api";
import type { AppConfig, AppConfigPatch } from "@/lib/types";

export type SettingsStatus = "loading" | "error" | "ready";

export interface SaveResult {
  ok: boolean;
  /** field → message, when the failure was a per-field 422. */
  fieldErrors?: Record<string, string>;
  /** form-level message (non-422 error, e.g. network/500). */
  formError?: string;
}

export interface UseSettings {
  config: AppConfig | null;
  status: SettingsStatus;
  errMsg: string;
  reload: () => void;
  /** PATCH a partial config; returns the outcome (parent shows per-field / form error). */
  save: (patch: AppConfigPatch) => Promise<SaveResult>;
}

export function useSettings(): UseSettings {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [status, setStatus] = useState<SettingsStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getSettings();
        if (!alive) return;
        if (res?.data == null) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setConfig(res.data);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  const save = useCallback(async (patch: AppConfigPatch): Promise<SaveResult> => {
    try {
      const res = await patchSettings(patch);
      // FAIL-CLOSED: trust the SERVER's returned config, not the local edit.
      if (res?.data == null) return { ok: false, formError: "phản hồi không hợp lệ" };
      setConfig(res.data);
      return { ok: true };
    } catch (e) {
      if (e instanceof ApiError) {
        const fieldErrors = e.fieldErrors();
        if (Object.keys(fieldErrors).length > 0) return { ok: false, fieldErrors };
        return { ok: false, formError: e.message };
      }
      return { ok: false, formError: (e as Error).message };
    }
  }, []);

  return { config, status, errMsg, reload, save };
}
