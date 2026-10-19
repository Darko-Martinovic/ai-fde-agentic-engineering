import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// UNDERCOVER_API points the proxy at another backend, as the end-to-end tests do.
const api = process.env.UNDERCOVER_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": api } },
  test: {
    environment: "jsdom",
    coverage: {
      include: ["src/**"],
      exclude: ["src/main.tsx"],
      thresholds: { statements: 80 },
    },
  },
});
