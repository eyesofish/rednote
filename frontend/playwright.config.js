import { defineConfig } from '@playwright/test'

const target = process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './tests',
  workers: 1,
  timeout: 60_000,
  reporter: 'list',
  use: {
    baseURL: target || 'http://127.0.0.1:5173',
    viewport: { width: 1280, height: 820 },
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'ui', testMatch: '**/ui.spec.js' },
    { name: 'live', testMatch: '**/live.spec.js' },
  ],
  webServer: target ? undefined : {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
  },
})
