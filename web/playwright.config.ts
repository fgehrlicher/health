import { defineConfig, devices } from "@playwright/test"

// End-to-end tests run their own API against the throwaway test database
// (see `make check-e2e`) and their own web server, never the real data.
const API_PORT = 8010
const WEB_PORT = 3010
const TEST_DATABASE_URL =
  process.env.TEST_DATABASE_URL ??
  "postgres://health:health@127.0.0.1:5432/health_test"

export default defineConfig({
  testDir: "e2e",
  // Tests share one database; run them one after another.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      // Binaries directly: `uv run` and `pnpm exec` do not pass Playwright's
      // stop signal on, which leaves servers running and the run hanging.
      command: `.venv/bin/health-api --port ${API_PORT}`,
      cwd: "..",
      url: `http://127.0.0.1:${API_PORT}/api/foods/facets`,
      env: { DATABASE_URL: TEST_DATABASE_URL },
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
    {
      command: `node_modules/.bin/vite dev --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      env: { HEALTH_API_URL: `http://127.0.0.1:${API_PORT}`, E2E: "1" },
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
  ],
})
