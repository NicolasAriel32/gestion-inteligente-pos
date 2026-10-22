import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  retries: 0,
  timeout: 90_000,
  use: {
    actionTimeout: 10000,
    headless: true,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    launchOptions: process.env.POS_TEST_CHROMIUM ? {
      executablePath: process.env.POS_TEST_CHROMIUM,
    } : {},
  },
})
