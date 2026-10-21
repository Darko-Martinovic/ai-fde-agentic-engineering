import { defineConfig } from "@playwright/test";
import { loadSettings, setting } from "./settings.config";

// The end-to-end tests run on their own ports and their own database, seeded
// fresh each run, from .env.defaults alone, so they never touch the data or
// servers from `npm run dev`.
const DEFAULTS_ONLY = ".env.defaults";
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
        BACKEND_PORT: setting("E2E_API_PORT"),
        BACKEND_RELOAD: "false",
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
