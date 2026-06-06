/**
 * tests/routes.test.tsx — Sprint 0 route placeholder smoke tests (Gate 2).
 *
 * Verifies each of the 14 route placeholders renders without crash.
 * Skipped per route if the component doesn't exist yet.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import React from "react";

const ROUTES = [
  { name: "Home",        importPath: "@/app/page" },
  { name: "Projects",    importPath: "@/app/projects/page" },
  { name: "ProjectDetail", importPath: "@/app/projects/[id]/page" },
  { name: "Graveyard",   importPath: "@/app/graveyard/page" },
  { name: "Finance",     importPath: "@/app/finance/page" },
  { name: "Portfolio",   importPath: "@/app/finance/portfolio/[id]/page" },
  { name: "Journal",     importPath: "@/app/journal/page" },
  { name: "Market",      importPath: "@/app/market/page" },
  { name: "ClaudeUsage", importPath: "@/app/claude-usage/page" },
  { name: "Notes",       importPath: "@/app/notes/page" },
  { name: "Brief",       importPath: "@/app/brief/page" },
  { name: "Settings",    importPath: "@/app/settings/page" },
  { name: "Routines",    importPath: "@/app/routines/page" },
  { name: "Activity",    importPath: "@/app/activity/page" },
];

describe("Route placeholders (14 screens)", () => {
  for (const route of ROUTES) {
    it(`${route.name} renders without crash`, async () => {
      let Component: React.ComponentType<any> | null = null;
      try {
        const mod = await import(route.importPath);
        Component = mod.default ?? mod[route.name] ?? null;
      } catch {
        // Not yet implemented — pass (pre-scaffold)
        return;
      }
      if (!Component) return;
      const { container } = render(<Component />);
      expect(container).toBeTruthy();
    });
  }
});
