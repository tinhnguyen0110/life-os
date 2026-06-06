/* ============================================================
   KpiCard — a single stat tile. Ported from mock screens-projects.js `.stat`
   (label .sl / value .sv / sub .sd). Used in the S2 summary grid (g-4) and S3.
   Value tone (pos/neg/mid/acc) is caller-driven via `tone`.
   ============================================================ */
import type { ReactNode } from "react";

/** Recognised value tones → helper class. Unknown strings → no tone class. */
const TONE_CLASS: Record<string, string> = {
  pos: "pos",
  neg: "neg",
  mid: "mid",
  acc: "acc",
  default: "",
};

export function KpiCard({
  label,
  value,
  sub,
  tone = "default",
}: {
  /** uppercase mono label (.sl). */
  label: string;
  /** the big stat (.sv) — number or pre-formatted node. */
  value: ReactNode;
  /** faint sub-line (.sd). Optional. */
  sub?: ReactNode;
  /** value tone: pos|neg|mid|acc (others ignored). Widened to string for callers. */
  tone?: string;
}) {
  const toneClass = TONE_CLASS[tone] ?? "";
  return (
    <div className="stat" data-testid="kpi-card">
      <span className="sl">{label}</span>
      <span className={`sv ${toneClass}`.trim()} data-testid="kpi-value">
        {value}
      </span>
      {sub != null && <span className="sd faint">{sub}</span>}
    </div>
  );
}
