import { defineConfig, devices } from '@playwright/test'

// Own port, so E2E never reuses a `pnpm dev` server on 5173 that talks to the real backend.
const PORT = 5174
const BASE_URL = `http://localhost:${PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `pnpm dev --port ${PORT} --strictPort`,
    url: BASE_URL,
    // E2E runs against the MSW mocks so it needs no backend.
    env: { VITE_ENABLE_MOCKS: 'true' },
    reuseExistingServer: !process.env.CI,
  },
})
