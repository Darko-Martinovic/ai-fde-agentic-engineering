import { defineConfig } from "@playwright/test";

// The end-to-end tests run on their own ports and their own database, seeded
// fresh each run, so they never touch the data or servers from `npm run dev`.
const API_PORT = "8001";
const DASHBOARD_PORT = "5174";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: `http://localhost:${DASHBOARD_PORT}` },
  webServer: [
    {
      command: `uv run -m backend.seed && uv run -m uvicorn backend.main:app --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      env: { UNDERCOVER_DB: "e2e/undercover-e2e.db" },
    },
    {
      command: `npx vite dashboard --port ${DASHBOARD_PORT} --strictPort`,
      url: `http://localhost:${DASHBOARD_PORT}`,
      reuseExistingServer: false,
      env: { UNDERCOVER_API: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
