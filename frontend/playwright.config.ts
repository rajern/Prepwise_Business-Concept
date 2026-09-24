import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'pnpm dev --host 127.0.0.1',
    env: {
      VITE_E2E_AUTH_ENABLED: 'true',
      VITE_ENTRA_TENANT_ID: '1a782388-bf90-4ea8-af8f-bcc755f5cd7e',
      VITE_ENTRA_TENANT_SUBDOMAIN: 'prepwisecustomers',
      VITE_ENTRA_SPA_CLIENT_ID: '00000000-0000-0000-0000-000000000000',
      VITE_ENTRA_API_SCOPE: 'api://prepwise-e2e/access_as_user',
    },
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
