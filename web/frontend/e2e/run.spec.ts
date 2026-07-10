import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * Stub /upload, /disag, /exceed so tests never reach real S3 or Lambda.
 * Pass per-call counters in if you need to assert order or payload.
 */
async function stubBackend(page: Page) {
	let putsSeen = 0;

	await page.route('**/upload', (route: Route) => {
		const key = `inputs/fake-client/fake-uuid/${++putsSeen}.bin`;
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				key,
				url: 'https://stub.s3.local/post-target',
				fields: { key, 'Content-Type': 'application/octet-stream' },
				expires_in: 300,
				max_bytes: 10 * 1024 * 1024
			})
		});
	});

	await page.route('https://stub.s3.local/post-target', (route: Route) =>
		route.fulfill({ status: 204, body: '' })
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
				output_key: 'runs/exceed/exc-99/output.svg',
				output_url: 'https://stub.s3.local/exceed.svg',
				report_key: 'runs/exceed/exc-99/output.rep',
				report_url: 'https://stub.s3.local/exceed.rep'
			})
		})
	);

	await page.route('**/convert', (route: Route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				run_id: 'conv-42',
				tool: 'convert',
				created_at: '2026-05-17T12:02:00Z',
				output_key: 'runs/convert/conv-42/output.mon',
				report_key: 'runs/convert/conv-42/output.rep',
				output_url: 'https://stub.s3.local/output.mon',
				report_url: 'https://stub.s3.local/convert.rep'
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

	test('algorithm options stay visible across methods; each toggle enables only where it applies', async ({
		page
	}) => {
		await page.goto('/run');

		// The options panel is always present; on method 0 the whole-month
		// toggle is greyed out (no single donor), not hidden.
		await expect(page.getByTestId('algo-options')).toBeVisible();
		await expect(page.getByTestId('whole-month-toggle')).toBeDisabled();

		// Methods 1, 2 and 5 each patch from one coherent donor → enabled.
		for (const m of [1, 2, 5]) {
			await page.getByTestId(`method-${m}`).check();
			await expect(page.getByTestId('whole-month-toggle')).toBeEnabled();
		}

		// The percent input only appears once the option is enabled.
		await expect(page.getByTestId('whole-month-percent')).not.toBeVisible();
		await page.getByTestId('whole-month-toggle').check();
		await expect(page.getByTestId('whole-month-percent')).toBeVisible();

		// Switching to a method without a single donor (3) disables the toggle
		// but keeps the panel — the setting survives to the next 1/2/5 pick.
		await page.getByTestId('method-3').check();
		await expect(page.getByTestId('whole-month-options')).toBeVisible();
		await expect(page.getByTestId('whole-month-toggle')).toBeDisabled();
		await page.getByTestId('method-5').check();
		await expect(page.getByTestId('whole-month-toggle')).toBeChecked();
		await expect(page.getByTestId('whole-month-percent')).toBeVisible();
	});

	test('fill-normalisation toggles are method-5 only; seam alone warns', async ({ page }) => {
		await page.goto('/run');

		// Not method 5 → both toggles visible but disabled.
		await expect(page.getByTestId('fdc-toggle')).toBeDisabled();
		await expect(page.getByTestId('seam-toggle')).toBeDisabled();

		await page.getByTestId('method-5').check();
		await expect(page.getByTestId('fdc-toggle')).toBeEnabled();
		await expect(page.getByTestId('seam-toggle')).toBeEnabled();

		// Seam blending without FDC mapping earns an inline caution.
		await page.getByTestId('seam-toggle').check();
		await expect(page.getByTestId('seam-warning')).toBeVisible();
		await page.getByTestId('fdc-toggle').check();
		await expect(page.getByTestId('seam-warning')).not.toBeVisible();
	});

	test('the actions row recaps the selected tool, method, and options', async ({ page }) => {
		await page.goto('/run');

		await expect(page.getByTestId('run-recap')).toContainText('Disag: method 0 — One file');

		// The recap tracks the method and any enabled algorithm options —
		// on tall forms the Run button scrolls far from the selections.
		await page.getByTestId('method-5').check();
		await page.getByTestId('fdc-toggle').check();
		await page.getByTestId('whole-month-toggle').check();
		const recap = page.getByTestId('run-recap');
		await expect(recap).toContainText('method 5 — Patch (exceedance)');
		await expect(recap).toContainText('FDC mapping');
		await expect(recap).toContainText('whole-month ≥50%');

		// Options that don't apply to the selected method drop out of the
		// recap even though their checkbox state persists.
		await page.getByTestId('method-0').check();
		await expect(recap).not.toContainText('FDC mapping');
		await expect(recap).not.toContainText('whole-month');

		await page.getByTestId('tool-exceed').check();
		await expect(recap).toContainText('Exceed: 20 intervals');
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

	test('exceed flow: monthly-only submit renders the curve preview + download links', async ({
		page
	}) => {
		await stubBackend(page);
		await page.goto('/run');

		await page.getByTestId('tool-exceed').check();
		await attachFile(page, 'drop-monthly', 'SINDILA.MON');

		await page.getByTestId('submit').click();

		const success = page.getByTestId('run-success');
		await expect(success).toBeVisible();
		await expect(page.getByTestId('download-report')).toBeVisible();
		// Exceed now returns an SVG curve as its output: shown inline + downloadable.
		await expect(page.getByTestId('curve-preview')).toBeVisible();
		await expect(page.getByTestId('download-output')).toBeVisible();
	});

	test('exceed seasonal builder: toggling months posts season groups', async ({ page }) => {
		await stubBackend(page);
		// Capture the /exceed payload (registered after stubBackend, so it
		// takes precedence) to confirm the season groups reach the API.
		let posted: { seasons?: Array<{ name: string; months: number[] }> } | null = null;
		await page.route('**/exceed', async (route: Route) => {
			posted = route.request().postDataJSON();
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					run_id: 'exc-seas',
					tool: 'exceed',
					created_at: '2026-05-17T12:02:00Z',
					output_key: 'runs/exceed/exc-seas/output.svg',
					output_url: 'https://stub.s3.local/exceed.svg',
					report_key: 'runs/exceed/exc-seas/output.rep',
					report_url: 'https://stub.s3.local/exceed.rep'
				})
			});
		});
		await page.goto('/run');

		await page.getByTestId('tool-exceed').check();
		await page.getByTestId('seasonal-toggle').check();
		// Default presets (Wet/Dry) render as season rows.
		await expect(page.getByTestId('season-row')).toHaveCount(2);

		// Toggling a month chip flips its pressed state.
		const janChip = page.getByTestId('season-row').first().getByRole('button', { name: 'Jan' });
		const before = await janChip.getAttribute('aria-pressed');
		await janChip.click();
		await expect(janChip).not.toHaveAttribute('aria-pressed', before ?? 'true');

		await attachFile(page, 'drop-monthly', 'SINDILA.MON');
		await page.getByTestId('submit').click();
		await expect(page.getByTestId('run-success')).toBeVisible();

		expect(posted, '/exceed received a payload').toBeTruthy();
		expect(Array.isArray(posted!.seasons), 'seasons is an array').toBeTruthy();
		expect(posted!.seasons!.length).toBeGreaterThanOrEqual(1);
		expect(posted!.seasons![0]).toHaveProperty('months');
	});

	test('switching to convert swaps the file pickers for a single .ans dropzone', async ({
		page
	}) => {
		await page.goto('/run');
		await page.getByTestId('tool-convert').check();
		await expect(page.getByTestId('drop-ans')).toBeVisible();
		await expect(page.getByTestId('drop-monthly')).toHaveCount(0);
		await expect(page.getByTestId('drop-daily1')).toHaveCount(0);
		// No method or intervals UI in convert mode.
		await expect(page.getByTestId('method-0')).toHaveCount(0);
		await expect(page.getByTestId('intervals-input')).toHaveCount(0);
	});

	test('convert flow: upload .ans → render .mon download link', async ({ page }) => {
		await stubBackend(page);
		await page.goto('/run?tool=convert');

		await expect(page.getByTestId('tool-convert')).toBeChecked();
		await attachFile(page, 'drop-ans', 'SAMPLE.ANS');
		await page.getByTestId('submit').click();

		const success = page.getByTestId('run-success');
		await expect(success).toBeVisible();
		await expect(success).toContainText(/conv-42/);
		await expect(page.getByTestId('download-output')).toHaveAttribute(
			'href',
			'https://stub.s3.local/output.mon'
		);
		await expect(page.getByTestId('download-output')).toContainText(/\.mon output/);
	});

	test('convert flow: submitting with no .ans file shows a friendly error', async ({ page }) => {
		await stubBackend(page);
		await page.goto('/run?tool=convert');

		await page.getByTestId('submit').click();
		await expect(page.getByTestId('run-error')).toContainText(/Source monthly file is required/);
	});
});
