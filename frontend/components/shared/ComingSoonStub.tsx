/* ============================================================
   ComingSoonStub — honest placeholder for a panel that's in the approved mock
   but whose backend isn't built yet (Claude quota S9, Brief S11, Activity S14).
   NEVER renders a fabricated number — a clearly-marked "sắp có" tile so the user
   sees the section exists (mock parity) without being shown fake data.
   ============================================================ */
import type { ReactNode } from "react";

export function ComingSoonStub({
  label,
  note,
  testId,
}: {
  /** kicker title, e.g. "Claude · quota". */
  label: string;
  /** the "sắp có" explanation — what's not wired yet. */
  note: ReactNode;
  testId?: string;
}) {
  return (
    <div className="card" data-testid={testId} data-stub>
      <div className="kicker" style={{ alignSelf: "flex-start" }}>
        {label}
      </div>
      <div className="hint" style={{ padding: "18px 8px", textAlign: "center" }}>
        Sắp có — {note}
      </div>
    </div>
  );
}
