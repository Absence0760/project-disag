import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * Stub /upload, /disag, /exceed so tests never reach real S3 or Lambda.
 * Pass per-call counters in if you need to assert order or payload.
 */
async function stubBackend(page: Page) {
	let putsSeen = 0;

	await page.route('**/upload', (route: Route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				key: `inputs/fake-uuid/${++putsSeen}.bin`,
				url: 'https://stub.s3.local/put-target',
				expires_in: 3600
			})
		})
	);

	await page.route('https://stub.s3.local/put-target', (route: Route) =>
		route.fulfill({ status: 200, body: '' })
	);

	await page.route('**/disag', (route: Route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				run_id: '1700000000-abcdef12',
				tool: 'disag',
				created_at: '2026-05-17T12:00:00Z',
				output_key: 'runs/disag/1700000000-abcdef12/output.day',
				report_key: 'runs/disag/1700000000-abcdef12/output.rep',
				output_url: 'https://stub.s3.local/output.day',
				report_url: 'https://stub.s3.local/output.rep'
			})
		})
	);

	await page.route('**/exceed', (route: Route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				run_id: 'exc-99',
				tool: 'exceed',
				created_at: '2026-05-17T12:01:00Z',
				report_key: 'runs/exceed/exc-99/output.rep',
				report_url: 'https://stub.s3.local/exceed.rep'
			})
		})
	);
}

async function attachFile(page: Page, testid: string, name: string) {
	const input = page.locator(`[data-testid="${testid}"] input[type=file]`);
	await input.setInputFiles({
		name,
		mimeType: 'application/octet-stream',
		buffer: Buffer.from('stub-content')
	});
}

test.describe('Run page', () => {
	test('defaults to disag + method 0 and shows the dropzones', async ({ page }) => {
		await page.goto('/run');

		await expect(page.getByRole('heading', { name: 'Run a job' })).toBeVisible();
		await expect(page.getByTestId('tool-disag')).toBeChecked();
		await expect(page.getByTestId('method-0')).toBeChecked();
		await expect(page.getByTestId('drop-monthly')).toBeVisible();
		await expect(page.getByTestId('drop-daily1')).toBeVisible();
		await expect(page.getByTestId('drop-daily2')).not.toBeVisible();
	});

	test('method 2 reveals the second daily dropzone, method 4 hides it again', async ({ page }) => {
		await page.goto('/run');

		await page.getByTestId('method-2').check();
		await expect(page.getByTestId('drop-daily2')).toBeVisible();

		await page.getByTestId('method-4').check();
		await expect(page.getByTestId('drop-daily2')).not.toBeVisible();
	});

	test('switching to exceed swaps method picker for intervals input', async ({ page }) => {
		await page.goto('/run');

		await page.getByTestId('tool-exceed').check();
		await expect(page.getByTestId('intervals-input')).toBeVisible();
		await expect(page.getByTestId('method-0')).toHaveCount(0);
	});

	test('submitting with no monthly file shows a friendly error', async ({ page }) => {
		await stubBackend(page);
		await page.goto('/run');

		await page.getByTestId('submit').click();
		await expect(page.getByTestId('run-error')).toContainText(/Monthly file is required/);
	});

	test('full disag flow: upload → run → render success with download links', async ({ page }) => {
		await stubBackend(page);
		await page.goto('/run');

		await attachFile(page, 'drop-monthly', 'SINDILA.MON');
		await attachFile(page, 'drop-daily1', 'RUKOKI-l.DAY');

		await page.getByTestId('submit').click();

		const success = page.getByTestId('run-success');
		await expect(success).toBeVisible();
		await expect(success).toContainText(/1700000000-abcdef12/);
		await expect(page.getByTestId('download-output')).toHaveAttribute(
			'href',
			'https://stub.s3.local/output.day'
		);
		await expect(page.getByTestId('download-report')).toHaveAttribute(
			'href',
			'https://stub.s3.local/output.rep'
		);
	});

	test('exceed flow: monthly-only submit renders report link, no output link', async ({ page }) => {
		await stubBackend(page);
		await page.goto('/run');

		await page.getByTestId('tool-exceed').check();
		await attachFile(page, 'drop-monthly', 'SINDILA.MON');

		await page.getByTestId('submit').click();

		const success = page.getByTestId('run-success');
		await expect(success).toBeVisible();
		await expect(page.getByTestId('download-report')).toBeVisible();
		await expect(page.getByTestId('download-output')).toHaveCount(0);
	});
});
