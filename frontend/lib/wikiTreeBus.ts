/* ============================================================
   #108 — wiki-tree refresh bus. A tiny module-level pub/sub so a write-through done in
   ONE component (import modal, capture form, note delete/restore, move) invalidates the
   tree/count query in ANOTHER (the persistent WikiExplorer in app/wiki/layout.tsx).

   THE BUG it fixes: the Explorer fetched the folder tree once + only refetched on a route
   CHANGE. A note created into a NEW folder (no navigation) left the Explorer showing the
   stale pre-write count (e.g. Projects=0) — the write looked like it failed. The BE was
   correct end-to-end (#101); this is purely the FE cross-component refresh wiring.

   Pattern: a monotonic version + listeners. Any tree-mutating write bumps the version on
   success (markWikiTreeStale); useWikiTree subscribes + refetches when it changes. Pure
   in-memory, SSR-safe (no window), no deps. The version lets a subscriber that mounts
   AFTER a bump still notice it (compare last-seen vs current) — avoids a missed-signal race.
   ============================================================ */

let version = 0;
const listeners = new Set<() => void>();

/** Bump the tree version + notify subscribers — call on a successful tree-mutating write
 *  (create / import / move-folder / delete / restore / bulk-delete). */
export function markWikiTreeStale(): void {
  version += 1;
  // copy to an array so a listener that unsubscribes mid-notify can't break iteration
  for (const fn of Array.from(listeners)) {
    try { fn(); } catch { /* a bad listener never blocks the others */ }
  }
}

/** Current tree version — a subscriber compares its last-seen value to detect a bump it
 *  may have missed (mounted just after a write). */
export function wikiTreeVersion(): number {
  return version;
}

/** Subscribe to tree-stale signals. Returns an unsubscribe fn. */
export function subscribeWikiTree(fn: () => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
