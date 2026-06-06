"use client";
/* ============================================================
   TickerTape — bottom fixed mono scroll. Green up / red down.
   Ported from mock shell.js tickerHTML() — doubled track for seamless CSS loop.
   Sprint 0: mock data (TICKER_MOCK); swapped for the /market feed in Sprint 4.
   Empty data → renders an empty tape (no crash).
   ============================================================ */
import { TICKER_MOCK, type TickerItem } from "@/lib/ticker-mock";

export function TickerTape({ items = TICKER_MOCK }: { items?: TickerItem[] }) {
  // Doubled so the -50% translate loop is seamless (matches mock one+one).
  const loop = items.length > 0 ? [...items, ...items] : [];

  return (
    <div className="tape" data-testid="ticker">
      <div className="tk">
        {loop.map((t, i) => (
          <span className="ti" key={`${t.sym}-${i}`}>
            <span className="sym">{t.sym}</span>
            <b>{t.px}</b>
            <span className={t.dir}>{t.chg}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
