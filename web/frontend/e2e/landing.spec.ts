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

	test('shows a card for each of the three tools', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('feature-disag')).toBeVisible();
		await expect(page.getByTestId('feature-exceed')).toBeVisible();
		await expect(page.getByTestId('feature-converter')).toBeVisible();

		await expect(page.getByTestId('feature-disag-cta')).toHaveAttribute('href', '/run?tool=disag');
		await expect(page.getByTestId('feature-exceed-cta')).toHaveAttribute(
			'href',
			'/run?tool=exceed'
		);
		await expect(page.getByTestId('feature-converter-cta')).toHaveAttribute(
			'href',
			'/run?tool=convert'
		);
	});

	test('Exceed tool card deep-links into /run with the right tool preselected', async ({
		page
	}) => {
		await page.goto('/');
		await page.getByTestId('feature-exceed-cta').click();
		await expect(page).toHaveURL(/\/run\?tool=exceed$/);
		await expect(page.getByTestId('tool-exceed')).toBeChecked();
	});

	test('Converter tool card deep-links into /run with the convert tool preselected', async ({
		page
	}) => {
		await page.goto('/');
		await page.getByTestId('feature-converter-cta').click();
		await expect(page).toHaveURL(/\/run\?tool=convert$/);
		await expect(page.getByTestId('tool-convert')).toBeChecked();
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
