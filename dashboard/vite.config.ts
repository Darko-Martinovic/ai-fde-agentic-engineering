import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { loadSettings, setting } from "../settings.config";

loadSettings(
  process.env.VITEST
    ? ".env.defaults"
    : (process.env.UNDERCOVER_ENV_FILES ?? ".env,.env.defaults"),
);

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(setting("DASHBOARD_PORT")),
    strictPort: true,
    proxy: { "/api": setting("UNDERCOVER_API") },
  },
  test: {
    environment: "jsdom",
    coverage: {
      include: ["src/**"],
      exclude: ["src/main.tsx"],
      thresholds: { statements: 80 },
    },
  },
});
