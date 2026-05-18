import { expect, test } from '@playwright/test';
import { fetchText, runDisag, uploadFixture, API, CLIENT_ID } from './_fixtures';

/**
 * Round-trips every disag method against the deterministic fixtures
 * under examples/methodN_demo/data/. The same fixtures are used by the
 * Python suite (tests/test_demo_methods.py and tests/test_e2e.py); the
 * assertions here are the visible-output subset of those tests —
 * report contents and file existence — so a regression in any of:
 *   - disag.algorithm
 *   - disag.files
 *   - disag.report
 *   - the web handler / local_server / S3 stub
 * shows up here.
 */

test.describe('@integration disag', () => {
	test('method 0 — one file, no patches expected', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'method0_demo', 'target.MON');
		const daily1Key = await uploadFixture(request, 'method0_demo', 'gauge_complete.DAY');

		const result = await runDisag(request, {
			method: 0,
			monthly_key: monthlyKey,
			daily1_key: daily1Key
		});

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('One disaggregator');
		// No patch-log lines for method 0 — it drops months instead of
		// patching. A patch-log line starts with "<year> <month>"; the
		// method-header text also contains "Patched with" so the regex
		// has to be anchored to a data line.
		expect(report).not.toMatch(/^\s*\d{4}\s+\d+.*Patched with/m);

		const output = await fetchText(request, result.output_url!);
		expect(output.length, '.day output non-empty').toBeGreaterThan(0);
	});

	test('method 0 with gaps — gap month is dropped, not patched', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'method0_demo', 'target.MON');
		const daily1Key = await uploadFixture(request, 'method0_demo', 'gauge_with_gap.DAY');

		const result = await runDisag(request, {
			method: 0,
			monthly_key: monthlyKey,
			daily1_key: daily1Key
		});

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('One disaggregator');
		// Gap month emits a "Missing" line, not a "Patched" line.
		expect(report).not.toMatch(/^\s*\d{4}\s+\d+.*Patched with/m);
	});

	test('method 1 — calendar patch logs the donor month', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'method1_demo', 'target.MON');
		const daily1Key = await uploadFixture(request, 'method1_demo', 'gauge_with_gap.DAY');

		const result = await runDisag(request, {
			method: 1,
			monthly_key: monthlyKey,
			daily1_key: daily1Key
		});

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('Patched with similar month');
		// The known gap is 2002-06; the patcher picks 2003-06 as donor
		// (closest absolute volume in the same calendar month). See
		// examples/method1_demo/README.md.
		expect(report).toMatch(/2002\s+6/);
		expect(report).toMatch(/Patched with 2003\s+6/);
	});

	test('method 2 — file patching, silent by design (day-level)', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'method2_demo', 'target.MON');
		const daily1Key = await uploadFixture(request, 'method2_demo', 'gauge_a.DAY');
		const daily2Key = await uploadFixture(request, 'method2_demo', 'gauge_b.DAY');

		const result = await runDisag(request, {
			method: 2,
			monthly_key: monthlyKey,
			daily1_key: daily1Key,
			daily2_key: daily2Key
		});

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('Patched with file 2');
		// PATCH_FILE substitutes day-by-day without an audit line — see
		// docs/algorithm.md and tests/test_demo_methods.py. The header
		// itself contains "Patched with file 2"; we only forbid real
		// per-month patch-log lines.
		expect(report).not.toMatch(/^\s*\d{4}\s+\d+.*Patched with/m);
	});

	test('method 3 — incremental (file1 − file2)', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'method3_demo', 'target.MON');
		const downstream = await uploadFixture(request, 'method3_demo', 'gauge_downstream.DAY');
		const upstream = await uploadFixture(request, 'method3_demo', 'gauge_upstream.DAY');

		const result = await runDisag(request, {
			method: 3,
			monthly_key: monthlyKey,
			daily1_key: downstream,
			daily2_key: upstream
		});

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('incremental runoff');

		const output = await fetchText(request, result.output_url!);
		// Incremental can be negative when upstream > downstream; just
		// assert the output is non-trivial.
		expect(output.length).toBeGreaterThan(200);
	});

	test('method 4 — even, no daily reference needed', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'method4_demo', 'target.MON');

		const result = await runDisag(request, { method: 4, monthly_key: monthlyKey });

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('Even distribution');
		expect(report).not.toMatch(/^\s*\d{4}\s+\d+.*Patched with/m);
	});

	test('method 5 — PATCH_EXCEED reports tier breakdown', async ({ request }) => {
		const monthlyKey = await uploadFixture(request, 'method5_demo', 'target.MON');
		const daily1Key = await uploadFixture(request, 'method5_demo', 'gauge_a_with_gaps.DAY');
		const daily2Key = await uploadFixture(request, 'method5_demo', 'gauge_b_partial.DAY');

		const result = await runDisag(request, {
			method: 5,
			monthly_key: monthlyKey,
			daily1_key: daily1Key,
			daily2_key: daily2Key
		});

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('exceedance-matched donor');
		// Tier summary lines come from disag.report — guarantees the
		// month-by-month breakdown landed.
		expect(report).toMatch(/Tier 1/);
		expect(report).toMatch(/Tier 2/);
		expect(report).toMatch(/Tier 3/);
	});

	test('/runs lists each completed run with its tool tag', async ({ request }) => {
		const list = await request.get(`${API}/runs`, { headers: { 'x-client-id': CLIENT_ID } });
		expect(list.ok()).toBeTruthy();
		const runs: Array<{ tool: string; run_id: string }> = await list.json();
		// At least the six prior tests should be present in this run.
		// (Other specs run before this one because Playwright sorts them
		// alphabetically and `disag.spec` runs in isolation under
		// `workers: 1`.)
		expect(runs.length).toBeGreaterThanOrEqual(6);
		expect(runs.every((r) => r.tool === 'disag')).toBeTruthy();
	});

	test('/runs is scoped to the calling client_id', async ({ request }) => {
		// A different (random) client_id must see zero of this spec's runs.
		const other = crypto.randomUUID();
		const list = await request.get(`${API}/runs`, { headers: { 'x-client-id': other } });
		expect(list.ok()).toBeTruthy();
		const runs: Array<unknown> = await list.json();
		expect(runs).toEqual([]);
	});

	test('rejects a foreign client_id submitting our key', async ({ request }) => {
		const monthly = await uploadFixture(request, 'method4_demo', 'target.MON');
		const other = crypto.randomUUID();
		const res = await request.post(`${API}/disag`, {
			data: { method: 4, monthly_key: monthly },
			headers: { 'x-client-id': other }
		});
		expect(res.status()).toBe(403);
		const body = await res.json();
		expect(body.error).toMatch(/does not belong/);
	});
});
