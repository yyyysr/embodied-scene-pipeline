import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  outputDir: 'node_modules/.cache/test-results',
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', launchOptions: {
    env: { ...process.env, DISPLAY: '' },
    args: ['--ozone-platform=headless', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  } },
  webServer: {
    command: 'npm run dev -- --port 5173',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
  },
})
