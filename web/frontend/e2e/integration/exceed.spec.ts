import { expect, test } from '@playwright/test';
import { fetchText, runExceed, uploadFixture, CLIENT_ID } from './_fixtures';

test.describe('@integration exceed', () => {
	test('monthly-only run produces a 12-month exceedance report', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'exceed_demo', 'target.MON');

		const result = await runExceed(request, { monthly_key: monthlyKey, intervals: 20 });

		const report = await fetchText(request, result.report_url);
		// exceed.files.write_exceedance_report emits a section per
		// calendar month; assert a handful are present rather than
		// pinning exact byte counts.
		// write_exceedance_report uppercases section headings:
		// "MONTHLY - JANUARY", "MONTHLY - JUNE", etc.
		for (const month of ['JANUARY', 'JUNE', 'DECEMBER']) {
			expect(report, `report mentions ${month}`).toContain(`MONTHLY - ${month}`);
		}
	});

	test('daily + monthly run produces monthly AND daily sections', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'exceed_demo', 'target.MON');
		const dailyKey = await uploadFixture(request, 'exceed_demo', 'gauge.DAY');

		const result = await runExceed(request, {
			monthly_key: monthlyKey,
			daily_key: dailyKey,
			intervals: 20
		});

		const report = await fetchText(request, result.report_url);
		// The CLI prefixes daily-derived blocks with "daily_<month>" — see
		// exceed/__main__.py. The report writer turns those into
		// "DAILY - <MONTH>" sections beneath the MONTHLY ones.
		expect(report).toContain('DAILY - JANUARY');
		expect(report).toContain('MONTHLY - JANUARY');
	});

	test('emits a downloadable SVG curve as the run output', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'exceed_demo', 'target.MON');

		const result = await runExceed(request, { monthly_key: monthlyKey, intervals: 20 });

		// The flow-frequency curve is now the primary output artifact.
		expect(result.output_key, 'output_key ends in .svg').toMatch(/\.svg$/);
		expect(result.output_url, 'output_url present').toBeTruthy();
		const svg = await fetchText(request, result.output_url as string);
		expect(svg).toContain('<svg');
		expect(svg).toContain('<polyline');
	});

	test('seasonal pooling produces one curve per season', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'exceed_demo', 'target.MON');

		const result = await runExceed(request, {
			monthly_key: monthlyKey,
			intervals: 20,
			seasons: [
				{ name: 'Wet', months: [10, 11, 12, 1, 2, 3] },
				{ name: 'Dry', months: [4, 5, 6, 7, 8, 9] }
			]
		});

		// Seasonal report headings are uppercased by write_seasonal_exceedance_report.
		const report = await fetchText(request, result.report_url);
		expect(report).toContain('Seasonal Exceedance Report');
		expect(report).toContain('WET');
		expect(report).toContain('DRY');
		// And the SVG legend names the seasons.
		const svg = await fetchText(request, result.output_url as string);
		expect(svg).toContain('Wet');
		expect(svg).toContain('Dry');
	});

	test('rejects an empty payload with 400', async ({ request }) => {
		const res = await request.post('http://127.0.0.1:8765/exceed', {
			data: { intervals: 20 },
			headers: { 'x-client-id': CLIENT_ID }
		});
		expect(res.status()).toBe(400);
		const body = await res.json();
		expect(body.error).toMatch(/monthly_key or daily_key/);
	});

	test('rejects requests missing the X-Client-Id header with 400', async ({ request }) => {
		const res = await request.post('http://127.0.0.1:8765/exceed', {
			data: { intervals: 20 }
		});
		expect(res.status()).toBe(400);
		const body = await res.json();
		expect(body.error).toMatch(/X-Client-Id/);
	});

	test('rejects out-of-range intervals with 400', async ({ request }) => {
		const monthly = await uploadFixture(request, 'method4_demo', 'target.MON');
		const res = await request.post('http://127.0.0.1:8765/exceed', {
			data: { monthly_key: monthly, intervals: 0 },
			headers: { 'x-client-id': CLIENT_ID }
		});
		expect(res.status()).toBe(400);
		const body = await res.json();
		expect(body.error).toMatch(/between 1 and 1000/);
	});
});
