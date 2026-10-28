import { defineConfig } from '@playwright/test';

// Smoke test runs against the real API. Start it first: uvicorn app.main:app --port 8001
export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  use: { baseURL: 'http://localhost:5174', trace: 'retain-on-failure' },
  webServer: {
    command: 'npx vite --port 5174 --strictPort',
    url: 'http://localhost:5174',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
