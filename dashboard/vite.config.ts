import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import {
  DEFAULTS_ONLY,
  loadSettings,
  optionalSetting,
  setting,
} from "../settings/settings.config";

export default defineConfig(({ mode }) => {
  // Tests read the committed defaults alone, never a developer's .env.
  loadSettings(mode === "test" ? DEFAULTS_ONLY : undefined);
  // `npm run dev` can't sign anyone in without the Supabase project in .env;
  // the unit tests stand in for auth.ts and leave it out
  const supabase = mode === "test" ? optionalSetting : setting;
  return {
    plugins: [react()],
    define: {
      "import.meta.env.VITE_MAX_AGENTS": JSON.stringify(setting("MAX_AGENTS")),
      // In .env for `npm run dev`, and set by the end-to-end run to its
      // stand-in for Supabase Auth
      "import.meta.env.VITE_SUPABASE_URL": JSON.stringify(
        supabase("VITE_SUPABASE_URL"),
      ),
      "import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY": JSON.stringify(
        supabase("VITE_SUPABASE_PUBLISHABLE_KEY"),
      ),
    },
    server: {
      host: setting("DASHBOARD_HOST"),
      port: Number(setting("DASHBOARD_PORT")),
      strictPort: true,
      proxy: { "/api": setting("UNDERCOVER_API") },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["src/setupTests.ts"],
      coverage: {
        include: ["src/**"],
        exclude: ["src/main.tsx", "src/setupTests.ts"],
        thresholds: { statements: 80 },
      },
    },
  };
});
