import { defineConfig } from "@playwright/test";
import {
  DEFAULTS_ONLY,
  loadSettings,
  setting,
} from "./settings/settings.config";
import { SIGNED_IN } from "./e2e/signed-in";

// The end-to-end tests run on their own ports and their own SQLite database, seeded
// fresh each run, from .env.defaults alone, so they never touch the data or
// servers from `npm run dev`. A setup project signs in as Dana Whitfield and
// as Marcus Oyelaran and keeps each browser's storage, and the tests run
// signed in as Dana unless they ask for Marcus.
loadSettings(DEFAULTS_ONLY);

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: setting("E2E_DASHBOARD_URL") },
  projects: [
    { name: "sign-in", testMatch: /sign-in\.setup\.ts/ },
    {
      name: "signed-in",
      dependencies: ["sign-in"],
      use: { storageState: SIGNED_IN.dana },
    },
  ],
  webServer: [
    {
      command: "uv run -m backend.seed && uv run -m backend",
      url: `${setting("E2E_API_URL")}/api/health`,
      reuseExistingServer: false,
      env: {
        UNDERCOVER_ENV_FILES: DEFAULTS_ONLY,
        UNDERCOVER_DB: setting("E2E_DB"),
        // Never a developer's Supabase or free model, even if the shell has them
        DATABASE_URL: "",
        MODEL_NAME: "",
        BACKEND_PORT: setting("E2E_API_PORT"),
        BACKEND_RELOAD: "false",
        UNDERCOVER_API: setting("E2E_API_URL"),
        UNDERCOVER_AGENT: setting("E2E_AGENT_URL"),
        VITE_SUPABASE_URL: setting("E2E_AUTH_URL"),
      },
    },
    {
      command: "node e2e/auth-stand-in.ts",
      url: `${setting("E2E_AUTH_URL")}/health`,
      reuseExistingServer: false,
      env: {
        E2E_AUTH_PORT: setting("E2E_AUTH_PORT"),
        AGENT_HOST: setting("AGENT_HOST"),
        E2E_HANDLER_PASSWORD: setting("E2E_HANDLER_PASSWORD"),
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
        VITE_SUPABASE_URL: setting("E2E_AUTH_URL"),
        VITE_SUPABASE_PUBLISHABLE_KEY: setting("E2E_PUBLISHABLE_KEY"),
      },
    },
  ],
});
