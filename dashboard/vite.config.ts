import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { DEFAULTS_ONLY, loadSettings, setting } from "../settings.config";

export default defineConfig(({ mode }) => {
  // Tests read the committed defaults alone, never a developer's .env.
  loadSettings(mode === "test" ? DEFAULTS_ONLY : undefined);
  return {
    plugins: [react()],
    server: {
      host: setting("DASHBOARD_HOST"),
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
  };
});
