import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In dev the UI runs on :5173 and proxies the API to the Express server on :8000.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000", "/healthz": "http://127.0.0.1:8000" } },
  build: { outDir: "dist", sourcemap: false },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
