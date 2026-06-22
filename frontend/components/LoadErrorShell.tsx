/* ============================================================
   LoadErrorShell — the shared loading / error gate that 30 screens hand-roll
   with the SAME shape (`{status, errMsg}` → a loading hint, an error hint + a
   reload button, else the body). #138-P1a extracts it so each screen stops
   re-implementing the branch; the screen passes its EXACT existing copy +
   testids as props, so the rendered output stays byte-identical.

   Behavior-preserving contract: this renders the SAME markup a screen wrote by
   hand —
     - status==="loading" → the loading node (the screen's exact label + testid)
     - status==="error"   → the error node (the screen's exact label, which may
                            interpolate {errMsg}/apiBase itself) + a reload button
                            when `reload` is given
     - otherwise          → children (the real screen body)
   The optional `section` props reproduce the `<section className data-screen>`
   wrapper a screen uses around its loading/error states.
   ============================================================ */
import type { ReactNode } from "react";

export type LoadErrorStatus = "loading" | "error" | "ready" | "idle" | string;

export function LoadErrorShell({
  status,
  loadingLabel,
  errorLabel,
  reload,
  reloadLabel = "Thử lại",
  loadingTestid,
  errorTestid,
  sectionClassName,
  dataScreen,
  children,
}: {
  /** the hook's status; only "loading"/"error" gate, anything else → children. */
  status: LoadErrorStatus;
  /** the screen's EXACT loading copy (string or node). */
  loadingLabel: ReactNode;
  /** the screen's EXACT error copy (string or node) — the screen interpolates
   *  its own {errMsg}/apiBase so the wording is preserved verbatim. */
  errorLabel: ReactNode;
  /** retry handler; when present an reload button is rendered after the error copy. */
  reload?: () => void;
  /** the retry button label (default "Thử lại" — the common copy). */
  reloadLabel?: string;
  /** testid on the loading hint (preserve the screen's existing one). */
  loadingTestid?: string;
  /** testid on the error hint (preserve the screen's existing one). */
  errorTestid?: string;
  /** when set, the loading/error states are wrapped in a <section> with this class. */
  sectionClassName?: string;
  /** the `data-screen` attribute on the wrapping section (e.g. "S5"). */
  dataScreen?: string;
  /** the real screen body, rendered when not loading/error. */
  children: ReactNode;
}) {
  if (status === "loading") {
    const node = (
      <div className="hint" style={{ padding: "24px 4px" }} data-testid={loadingTestid}>
        {loadingLabel}
      </div>
    );
    return sectionClassName !== undefined || dataScreen !== undefined
      ? <section className={sectionClassName} data-screen={dataScreen}>{node}</section>
      : node;
  }

  if (status === "error") {
    const node = (
      <div className="hint neg" style={{ padding: "24px 4px" }} data-testid={errorTestid}>
        {errorLabel}
        {reload && (
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>
            {reloadLabel}
          </button>
        )}
      </div>
    );
    return sectionClassName !== undefined || dataScreen !== undefined
      ? <section className={sectionClassName} data-screen={dataScreen}>{node}</section>
      : node;
  }

  return <>{children}</>;
}
