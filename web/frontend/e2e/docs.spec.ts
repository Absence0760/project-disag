import { expect, test } from '@playwright/test';

test.describe('Docs page', () => {
	test('renders the headline sections and the on-page contents', async ({ page }) => {
		await page.goto('/docs');

		await expect(page).toHaveTitle(/Docs/);
		await expect(page.getByRole('heading', { level: 1 })).toContainText(/How Disag-MD works/);

		// Every documented section anchor exists.
		for (const id of [
			'big-picture',
			'how-a-run-works',
			'disaggregation',
			'methods',
			'exceedance',
			'file-formats',
			'deeper'
		]) {
			await expect(page.locator(`#${id}`)).toBeAttached();
		}
	});

	test('lists all six disaggregation methods', async ({ page }) => {
		await page.goto('/docs');
		await expect(page.locator('.method-cards .method')).toHaveCount(6);
	});

	test('is reachable from the primary nav and highlights as active', async ({ page }) => {
		await page.goto('/');
		await page.getByTestId('nav-docs').click();
		await expect(page).toHaveURL(/\/docs$/);
		await expect(page.getByTestId('nav-docs')).toHaveClass(/active/);
	});

	test('renders a rendered markdown doc page with sidebar and rewritten links', async ({
		page
	}) => {
		await page.goto('/docs/problem');

		// Title comes from the markdown H1, body is rendered prose.
		await expect(page.getByRole('heading', { level: 1 })).toContainText(
			/What problem does this project solve/
		);
		await expect(page.locator('.prose table')).not.toHaveCount(0);

		// Intra-doc markdown links were rewritten to in-app routes.
		await expect(page.locator('.prose a[href="/docs/algorithm"]').first()).toBeVisible();

		// Sidebar lists sibling docs and lets you navigate between them.
		await page.locator('.sidebar a', { hasText: 'Exceedance Analysis' }).click();
		await expect(page).toHaveURL(/\/docs\/exceed$/);
		await expect(page.getByRole('heading', { level: 1 })).toContainText(/Exceedance/);
	});

	test('the overview "Go deeper" cards link into the rendered doc pages', async ({ page }) => {
		await page.goto('/docs');
		await page.locator('#deeper a[href="/docs/method5"]').click();
		await expect(page).toHaveURL(/\/docs\/method5$/);
		await expect(page.getByRole('heading', { level: 1 })).toContainText(/Method 5/);
	});
});
