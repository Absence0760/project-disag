/**
 * Browser-driven end-to-end coverage for the three tools.
 *
 * The other integration specs (disag.spec.ts, exceed.spec.ts,
 * convert.spec.ts) talk to the API directly with `request.post(...)`,
 * proving the backend works. This file proves the *full* path works:
 * SPA load → tool radio → file picker → submit → success card →
 * download link → real bytes back out of the local S3 stub.
 *
 * The Vite preview server proxies /api/* to the integration backend
 * on :8765 (see vite.config.ts preview.proxy). Each test gets its own
 * browser context, so each gets a fresh client_id from the SPA's
 * localStorage bootstrap — no cross-test pollution of /runs.
 */

import { expect, test } from '@playwright/test';
import { API, fixturePath } from './_fixtures';

async function attachFixture(
	page: import('@playwright/test').Page,
	dropzoneTestid: string,
	demo: string,
	filename: string
): Promise<void> {
	const input = page.locator(`[data-testid="${dropzoneTestid}"] input[type=file]`);
	await input.setInputFiles(fixturePath(demo, filename));
}

async function waitForSuccess(
	page: import('@playwright/test').Page
): Promise<{ outputUrl: string | null; reportUrl: string }> {
	const success = page.getByTestId('run-success');
	// Real backend on Lambda-sized work — most runs finish in a few
	// hundred ms, but give it room so a slow demo box doesn't flake.
	await expect(success).toBeVisible({ timeout: 20_000 });
	const reportUrl = await page.getByTestId('download-report').getAttribute('href');
	expect(reportUrl, 'report url present in DOM').toBeTruthy();
	const outputLocator = page.getByTestId('download-output');
	const outputUrl = (await outputLocator.count()) ? await outputLocator.getAttribute('href') : null;
	return { outputUrl, reportUrl: reportUrl as string };
}

test.describe('@integration browser', () => {
	test('Disag method 0: pick files in the UI, submit, download a real .day output', async ({
		page,
		request
	}) => {
		await page.goto('/run');
		await expect(page.getByTestId('tool-disag')).toBeChecked();
		await expect(page.getByTestId('method-0')).toBeChecked();

		await attachFixture(page, 'drop-monthly', 'method0_demo', 'target.MON');
		await attachFixture(page, 'drop-daily1', 'method0_demo', 'gauge_complete.DAY');

		await page.getByTestId('submit').click();
		const { outputUrl, reportUrl } = await waitForSuccess(page);
		expect(outputUrl, '.day output link present').toBeTruthy();
		expect(outputUrl).toMatch(/output\.day/);
		await expect(page.getByTestId('download-output')).toContainText(/\.day output/);

		// Fetch the actual bytes and confirm they look like a .day file.
		const outputBody = await (await request.get(outputUrl as string)).text();
		expect(outputBody.length, '.day body non-empty').toBeGreaterThan(0);

		const reportBody = await (await request.get(reportUrl)).text();
		expect(reportBody).toContain('One disaggregator');
	});

	test('Exceed: switch tool in the UI, submit monthly-only, get a .rep with month sections', async ({
		page,
		request
	}) => {
		await page.goto('/run');
		await page.getByTestId('tool-exceed').check();
		await expect(page.getByTestId('intervals-input')).toBeVisible();
		// Method picker must not be visible in exceed mode.
		await expect(page.getByTestId('method-0')).toHaveCount(0);

		await attachFixture(page, 'drop-monthly', 'exceed_demo', 'target.MON');

		await page.getByTestId('submit').click();
		const { outputUrl, reportUrl } = await waitForSuccess(page);
		// Exceed has no output file — only the report.
		expect(outputUrl, 'exceed has no output download').toBeNull();

		const reportBody = await (await request.get(reportUrl)).text();
		// write_exceedance_report emits a section per calendar month.
		expect(reportBody).toContain('MONTHLY - JANUARY');
		expect(reportBody).toContain('MONTHLY - JUNE');
		expect(reportBody).toContain('MONTHLY - DECEMBER');
	});

	test('Convert: switch tool in the UI, upload .ans, get a real .mon back', async ({
		page,
		request
	}) => {
		await page.goto('/run?tool=convert');
		await expect(page.getByTestId('tool-convert')).toBeChecked();
		// Convert mode collapses the multi-file UI down to a single .ans
		// dropzone with no method picker / intervals input.
		await expect(page.getByTestId('drop-ans')).toBeVisible();
		await expect(page.getByTestId('drop-monthly')).toHaveCount(0);
		await expect(page.getByTestId('drop-daily1')).toHaveCount(0);
		await expect(page.getByTestId('method-0')).toHaveCount(0);
		await expect(page.getByTestId('intervals-input')).toHaveCount(0);

		await attachFixture(page, 'drop-ans', 'convert_demo', 'SAMPLE.ANS');

		await page.getByTestId('submit').click();
		const { outputUrl, reportUrl } = await waitForSuccess(page);
		expect(outputUrl, '.mon output link present').toBeTruthy();
		expect(outputUrl).toMatch(/output\.mon/);
		await expect(page.getByTestId('download-output')).toContainText(/\.mon output/);

		const monBody = await (await request.get(outputUrl as string)).text();
		// All three hydro years from SAMPLE.ANS must round-trip, including
		// the flood-year row whose 8-char columns touched with no
		// separator (9999.99 14639.12 13670.74).
		expect(monBody).toMatch(/^\s*1990\s/m);
		expect(monBody).toMatch(/^\s*1991\s/m);
		expect(monBody).toMatch(/^\s*1992\s/m);
		expect(monBody).toMatch(/1991.*9999\.990.*14639\.120.*13670\.740/);

		const reportBody = await (await request.get(reportUrl)).text();
		expect(reportBody).toContain('Rows written: 3');
	});
});

// Silence "unused import" — kept for symmetry with sibling specs.
void API;
