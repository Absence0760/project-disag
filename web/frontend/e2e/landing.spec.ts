import { expect, test } from '@playwright/test';

test.describe('Landing page', () => {
	test('renders hero, badges, and primary CTAs', async ({ page }) => {
		await page.goto('/');

		await expect(page).toHaveTitle(/Disag-MD/);
		await expect(page.getByRole('heading', { level: 1 })).toContainText(/Disaggregate/);
		await expect(page.getByTestId('hero-badge')).toBeVisible();
		await expect(page.getByTestId('hero-primary')).toHaveAttribute('href', '/run');
		await expect(page.getByTestId('hero-secondary')).toHaveAttribute('href', '/history');
	});

	test('feature cards link to /run and /history', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('feature-run')).toBeVisible();
		await expect(page.getByTestId('feature-history')).toBeVisible();

		await page.getByTestId('feature-run').click();
		await expect(page).toHaveURL(/\/run$/);
	});

	test('primary nav highlights the current route', async ({ page }) => {
		await page.goto('/run');
		const runLink = page.getByTestId('nav-run');
		await expect(runLink).toHaveClass(/active/);

		await page.getByTestId('nav-history').click();
		await expect(page).toHaveURL(/\/history$/);
		await expect(page.getByTestId('nav-history')).toHaveClass(/active/);
	});

	test('renders all 6 disaggregation methods in the overview', async ({ page }) => {
		await page.goto('/');
		const items = page.locator('.method-list li');
		await expect(items).toHaveCount(6);
		await expect(items.first()).toContainText('0 · One file');
		await expect(items.last()).toContainText('5 · Patch (exceedance)');
	});
});
