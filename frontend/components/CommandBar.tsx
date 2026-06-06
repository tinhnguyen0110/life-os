"use client";
/* ============================================================
   CommandBar — cockpit input, `>` prefix. ⌘K / Ctrl+K focuses it.
   Command grammar ported from mock interactions.js runCommand() — NO AI (ARCH §11):
     open <project>   → /projects (detail wiring lands with Projects sprint)
     dca ...          → /journal
     run <routine>    → /activity
     note ...         → /notes
   Unknown → inline hint. Sprint 0: navigation + hint only; real actions wire later.
   ============================================================ */
import { useEffect, useRef, useState } from "react";
import { useSafeRouter } from "@/lib/useNav";

export interface CommandResult {
  ok: boolean;
  message: string;
  route?: string;
}

/** Pure command parser — unit-testable without the DOM. */
export function parseCommand(raw: string): CommandResult {
  const v = (raw || "").trim();
  if (!v) return { ok: false, message: "" };
  const low = v.toLowerCase();

  if (low.startsWith("open ")) {
    const id = low.slice(5).trim();
    if (id) return { ok: true, message: `Mở dự án "${id}"`, route: "/projects" };
  }
  if (low.startsWith("dca")) {
    return { ok: true, message: "✓ Ghi nhận lệnh DCA — mở Nhật ký để xác nhận", route: "/journal" };
  }
  if (low.startsWith("run")) {
    return { ok: true, message: "▶ Kích hoạt routine — xem Activity Feed", route: "/activity" };
  }
  if (low.startsWith("note")) {
    return { ok: true, message: "Mở Ghi chú", route: "/notes" };
  }
  return {
    ok: false,
    message: "Lệnh chưa rõ — thử: open <dự án> · dca btc 2000 · run morning-brief · note …",
  };
}

// `open` is accepted for API compatibility (mock had a palette overlay); the
// Sprint 0 command bar is an always-visible inline input, so it's a no-op.
export function CommandBar(_props: { open?: boolean } = {}) {
  const router = useSafeRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [hint, setHint] = useState<string>("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    const result = parseCommand(e.currentTarget.value);
    if (!result.message) return; // empty input
    setHint(result.message);
    if (result.route) {
      e.currentTarget.value = "";
      router.push(result.route);
    }
  }

  return (
    <div className="cmdbar" role="search">
      <span className="pr" aria-hidden="true">
        &gt;
      </span>
      <input
        ref={inputRef}
        type="text"
        aria-label="Command bar"
        data-command-input
        placeholder="dca btc 2000 · open mcp-wrapper · run morning-brief · note …"
        onKeyDown={onKeyDown}
        onChange={() => hint && setHint("")}
      />
      {hint && (
        <span className="hint" data-testid="cmd-hint">
          {hint}
        </span>
      )}
      <kbd>⌘K</kbd>
    </div>
  );
}
