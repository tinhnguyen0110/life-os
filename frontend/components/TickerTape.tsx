"use client";
/* ============================================================
   TickerTape — bottom fixed mono scroll. Green up / red down.
   Ported from mock shell.js tickerHTML() — doubled track for seamless CSS loop.

   Two entry points:
   - <TickerTape items={...} />  — pure presentational (default = TICKER_MOCK).
     Stays prop-driven so component tests render deterministically.
   - <LiveTickerTape />          — fetches /market via useMarket and feeds the
     live watchlist in, falling back to TICKER_MOCK on error so the tape never
     blanks. This is what the shell mounts.

   Empty data → renders an empty tape (no crash).
   ============================================================ */
import { TICKER_MOCK, type TickerItem } from "@/lib/ticker-mock";
import { useMarket } from "@/lib/useMarket";

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

/** Live-wired tape — pulls /market, falls back to TICKER_MOCK on error/empty. */
export function LiveTickerTape() {
  const { tickerItems } = useMarket();
  return <TickerTape items={tickerItems} />;
}
