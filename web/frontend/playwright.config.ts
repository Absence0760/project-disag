import { defineConfig, devices } from '@playwright/test';

const port = 4173;
const apiPort = 8765;

// Two suites, two server stacks:
//   • mocked        — vite preview only; backend is page.route()-stubbed.
//   • integration   — vite preview + local_server.py with LOCAL_S3=1, so
//                     real disag/exceed code runs against real fixture
//                     files on disk. No AWS required.
// Run via:
//   pnpm e2e                  → mocked (fast, no Python needed)
//   pnpm e2e:integration      → integration (boots local_server too)
//   pnpm e2e:all              → both projects

const isIntegration = process.env.PLAYWRIGHT_PROJECT === 'integration';

export default defineConfig({
	testDir: './e2e',
	outputDir: './e2e/.results',
	fullyParallel: !isIntegration,
	// Integration specs talk to a single backend process; running them
	// in parallel would race on the shared /tmp store and confuse the
	// /runs listing. Mocked specs have no shared state.
	workers: isIntegration ? 1 : process.env.CI ? 1 : undefined,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
	use: {
		baseURL: `http://127.0.0.1:${port}`,
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure'
	},
	projects: isIntegration
		? [
				{
					name: 'integration-chromium',
					testMatch: /integration\/.*\.spec\.ts$/,
					use: { ...devices['Desktop Chrome'] }
				}
			]
		: [
				{
					name: 'chromium',
					testMatch: /^(?!.*integration\/).*\.spec\.ts$/,
					use: { ...devices['Desktop Chrome'] }
				},
				{
					name: 'firefox',
					testMatch: /^(?!.*integration\/).*\.spec\.ts$/,
					use: { ...devices['Desktop Firefox'] }
				}
			],
	webServer: isIntegration
		? [
				{
					command: `pnpm preview --host 127.0.0.1 --port ${port} --strictPort`,
					url: `http://127.0.0.1:${port}`,
					reuseExistingServer: !process.env.CI,
					stdout: 'pipe',
					stderr: 'pipe',
					timeout: 120_000
				},
				{
					// The shim that wraps handler.py with an on-disk S3 stub.
					// Pass LOCAL_S3=1 so boto3 is swapped for the filesystem
					// fake before the first request lands. The `rm -rf` keeps
					// every integration run starting from a clean store so
					// /runs listings are deterministic.
					command: `bash -lc 'cd ../.. && rm -rf web/backend/.local-s3 && LOCAL_S3=1 LOCAL_S3_ROOT=$(pwd)/web/backend/.local-s3 PORT=${apiPort} web/backend/.venv/bin/python web/backend/local_server.py'`,
					url: `http://127.0.0.1:${apiPort}/runs`,
					reuseExistingServer: !process.env.CI,
					stdout: 'pipe',
					stderr: 'pipe',
					timeout: 30_000
				}
			]
		: {
				command: `pnpm preview --host 127.0.0.1 --port ${port} --strictPort`,
				url: `http://127.0.0.1:${port}`,
				reuseExistingServer: !process.env.CI,
				stdout: 'pipe',
				stderr: 'pipe',
				timeout: 120_000
			}
});
