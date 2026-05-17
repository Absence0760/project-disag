import { expect, test, type Route } from '@playwright/test';

test.describe('History page', () => {
	test('shows a skeleton while loading, then the empty state when /runs returns []', async ({
		page
	}) => {
		// Hold the response so the loading state is observable.
		let release: (() => void) | undefined;
		const gate = new Promise<void>((resolve) => (release = resolve));

		await page.route('**/runs', async (route: Route) => {
			await gate;
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify([])
			});
		});

		await page.goto('/history');
		await expect(page.getByTestId('history-loading')).toBeVisible();

		release!();
		await expect(page.getByTestId('history-empty')).toBeVisible();
		await expect(page.getByTestId('history-empty')).toContainText(/No runs yet/);
	});

	test('renders a populated table with newest-first order', async ({ page }) => {
		await page.route('**/runs', (route: Route) =>
			route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify([
					{
						run_id: 'newer-run',
						tool: 'disag',
						created_at: '2026-05-17T12:30:00Z',
						size_bytes: 24576
					},
					{
						run_id: 'older-run',
						tool: 'exceed',
						created_at: '2026-05-16T08:00:00Z',
						size_bytes: 4096
					}
				])
			})
		);

		await page.goto('/history');

		const rows = page.locator('tbody tr');
		await expect(rows).toHaveCount(2);
		await expect(rows.nth(0)).toContainText('newer-run');
		await expect(rows.nth(0)).toContainText('disag');
		await expect(rows.nth(1)).toContainText('older-run');
		await expect(rows.nth(1)).toContainText('exceed');
	});

	test('surfaces a clear error when /runs fails', async ({ page }) => {
		await page.route('**/runs', (route: Route) =>
			route.fulfill({
				status: 500,
				contentType: 'application/json',
				body: JSON.stringify({ error: 'boto3 exploded' })
			})
		);

		await page.goto('/history');

		await expect(page.getByTestId('history-error')).toBeVisible();
		await expect(page.getByTestId('history-error')).toContainText(/boto3 exploded/);
	});
});
