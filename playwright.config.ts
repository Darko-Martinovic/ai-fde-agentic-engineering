import { defineConfig } from "@playwright/test";
import {
  DEFAULTS_ONLY,
  loadSettings,
  setting,
} from "./settings/settings.config";

// The end-to-end tests run on their own ports and their own SQLite database, seeded
// fresh each run, from .env.defaults alone, so they never touch the data or
// servers from `npm run dev`.
loadSettings(DEFAULTS_ONLY);

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: setting("E2E_DASHBOARD_URL") },
  webServer: [
    {
      command: "uv run -m backend.seed && uv run -m backend",
      url: `${setting("E2E_API_URL")}/api/health`,
      reuseExistingServer: false,
      env: {
        UNDERCOVER_ENV_FILES: DEFAULTS_ONLY,
        UNDERCOVER_DB: setting("E2E_DB"),
        // Never a developer's Supabase, even if DATABASE_URL is in the shell
        DATABASE_URL: "",
        BACKEND_PORT: setting("E2E_API_PORT"),
        BACKEND_RELOAD: "false",
        UNDERCOVER_API: setting("E2E_API_URL"),
        UNDERCOVER_AGENT: setting("E2E_AGENT_URL"),
      },
    },
    {
      command: "node e2e/agent-stand-in.ts",
      url: `${setting("E2E_AGENT_URL")}/api/health`,
      reuseExistingServer: false,
      env: {
        E2E_AGENT_PORT: setting("E2E_AGENT_PORT"),
        AGENT_HOST: setting("AGENT_HOST"),
      },
    },
    {
      command: "npx vite dashboard",
      url: setting("E2E_DASHBOARD_URL"),
      reuseExistingServer: false,
      env: {
        UNDERCOVER_ENV_FILES: DEFAULTS_ONLY,
        DASHBOARD_PORT: setting("E2E_DASHBOARD_PORT"),
        UNDERCOVER_API: setting("E2E_API_URL"),
      },
    },
  ],
});
