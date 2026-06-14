import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    // 12s > the MOC hang-guard test's deliberate 8s withTimeout (W5b). The default
    // 5s fired on cold-worker first runs before the per-test override took effect,
    // causing a first-run-only flake on moc.test.tsx (tester finding, W5b).
    testTimeout: 12000,
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
