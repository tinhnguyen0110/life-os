"use client";
/* ============================================================
   Wiki vault · StatTile (extracted from page.tsx, #138-P2 — pure MOVE, no logic
   change). A single stat tile in the vault overview grid. Stateless.
   ============================================================ */
export function StatTile({ label, value, sub, cls }: { label: string; value: string | number; sub: string; cls?: string }) {
  return (
    <div className="wtile" data-testid="wtile">
      <span className="wtile-l">{label}</span>
      <span className={`wtile-v ${cls ?? ""}`} data-testid="wtile-v">{value}</span>
      <span className="wtile-s">{sub}</span>
    </div>
  );
}
