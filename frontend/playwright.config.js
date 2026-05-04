import { defineConfig, devices } from '@playwright/test';

const isCI = Boolean(globalThis.process?.env?.CI);

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: true,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5183',
    trace: 'on-first-retry',
  },
  webServer: {
    // Use npm so CI works without an extra pnpm install step. Local devs
    // can still run `pnpm dev` themselves; reuseExistingServer picks it up.
    command: 'npm run dev -- --host 127.0.0.1',
    url: 'http://127.0.0.1:5183',
    reuseExistingServer: !isCI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
