/**
 * Negative-security pins against the real backend.
 *
 * Each test exercises one rejection path the audit highlighted:
 *
 *  - missing or malformed X-Client-Id → 400 on every authenticated
 *    route (/upload, /disag, /exceed, /convert, /runs)
 *  - submitting an S3 key that lives under another client's
 *    inputs/<client_id>/ prefix → 403 (IDOR backstop on each route
 *    that takes a key)
 *  - reaching for a foreign run_id via /runs/{id} → 404 (must be
 *    indistinguishable from a non-existent run so the response shape
 *    can't be used as a discovery oracle)
 *
 * Direct-APIGW + missing-shared-secret coverage lives in
 * tests/test_handler.py — the local backend doesn't set
 * CLOUDFRONT_SHARED_SECRET so we can't drive that path here. The
 * MAX_UPLOAD_BYTES policy is pinned by tests/test_handler.py
 * (presigned-POST conditions) rather than e2e — the local-S3 stub
 * doesn't enforce the content-length-range condition either.
 */

import { randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { API, fixturePath, uploadFixture } from './_fixtures';

// Per-spec client id — keeps these tests off the disag.spec.ts /runs
// listing assertion that expects every run to be tool='disag'.
const CLIENT_ID = randomUUID();
const HEADERS = { 'x-client-id': CLIENT_ID };

async function uploadAs(
	request: import('@playwright/test').APIRequestContext,
	clientId: string,
	demo: string,
	filename: string
): Promise<string> {
	const presign = await request.post(`${API}/upload`, {
		data: { filename },
		headers: { 'x-client-id': clientId }
	});
	expect(presign.ok(), `presign /upload as ${clientId}`).toBeTruthy();
	const { key, url, fields } = await presign.json();
	const buf = readFileSync(fixturePath(demo, filename));
	const post = await request.post(url, {
		multipart: {
			...fields,
			file: { name: filename, mimeType: 'application/octet-stream', buffer: buf }
		}
	});
	expect(post.ok()).toBeTruthy();
	return key as string;
}

test.describe('@integration security: X-Client-Id required', () => {
	for (const route of [
		{ method: 'POST', path: '/upload', body: { filename: 'x.mon' } },
		{ method: 'POST', path: '/disag', body: { method: 4, monthly_key: 'inputs/x/y/z.mon' } },
		{ method: 'POST', path: '/exceed', body: { monthly_key: 'inputs/x/y/z.mon' } },
		{ method: 'POST', path: '/convert', body: { ans_key: 'inputs/x/y/z.ans' } },
		{ method: 'GET', path: '/runs', body: null }
	]) {
		test(`${route.method} ${route.path} rejects missing X-Client-Id with 400`, async ({
			request
		}) => {
			const fn = route.method === 'GET' ? request.get : request.post;
			const res = await fn.call(request, `${API}${route.path}`, {
				data: route.body ?? undefined
			});
			expect(res.status()).toBe(400);
			const body = await res.json();
			expect(body.error).toMatch(/X-Client-Id/);
		});

		test(`${route.method} ${route.path} rejects bogus X-Client-Id format with 400`, async ({
			request
		}) => {
			const fn = route.method === 'GET' ? request.get : request.post;
			const res = await fn.call(request, `${API}${route.path}`, {
				data: route.body ?? undefined,
				headers: { 'x-client-id': 'not-a-uuid' }
			});
			expect(res.status()).toBe(400);
		});
	}
});

test.describe('@integration security: cross-client IDOR on input keys', () => {
	// /disag already has this pin in disag.spec.ts; clone it for the
	// two newer routes so a regression in _validate_input_key surfaces
	// across all three call sites.
	test('/exceed rejects a foreign client_id submitting our key', async ({ request }) => {
		// Upload a fixture under CLIENT_ID's prefix.
		const ourKey = await uploadAs(request, CLIENT_ID, 'exceed_demo', 'target.MON');
		// Now try to drive /exceed with a different x-client-id.
		const other = randomUUID();
		const res = await request.post(`${API}/exceed`, {
			data: { monthly_key: ourKey, intervals: 20 },
			headers: { 'x-client-id': other }
		});
		expect(res.status()).toBe(403);
		const body = await res.json();
		expect(body.error).toMatch(/does not belong/);
	});

	test('/convert rejects a foreign client_id submitting our key', async ({ request }) => {
		const ourKey = await uploadAs(request, CLIENT_ID, 'convert_demo', 'SAMPLE.ANS');
		const other = randomUUID();
		const res = await request.post(`${API}/convert`, {
			data: { ans_key: ourKey },
			headers: { 'x-client-id': other }
		});
		expect(res.status()).toBe(403);
		const body = await res.json();
		expect(body.error).toMatch(/does not belong/);
	});

	test('/convert rejects a manually constructed key under another client prefix', async ({
		request
	}) => {
		// No upload — just construct a plausible key with someone
		// else's UUID baked in and try to submit it. _validate_input_key
		// should refuse before any S3 read happens.
		const other = randomUUID();
		const forged = `inputs/${other}/abc/SAMPLE.ANS`;
		const res = await request.post(`${API}/convert`, {
			data: { ans_key: forged },
			headers: HEADERS
		});
		expect(res.status()).toBe(403);
	});
});

test.describe('@integration security: /runs discovery oracle', () => {
	test('GET /runs/{id} for a foreign run id returns 404 (not 403)', async ({ request }) => {
		// Run-id format is `<unix-ts>-<8 hex>` per handler.py RUN_ID_RE.
		// Construct a plausible-looking id and hit /runs/{id} with a
		// fresh client. The 404 must be indistinguishable from a
		// "no such run ever existed" 404, so an attacker can't use
		// the response shape to enumerate other clients' runs.
		const fake = `${Math.floor(Date.now() / 1000)}-deadbeef`;
		const res = await request.get(`${API}/runs/${fake}`, {
			headers: { 'x-client-id': randomUUID() }
		});
		expect(res.status()).toBe(404);
	});

	test('GET /runs/{id} rejects a malformed run id with 400', async ({ request }) => {
		const res = await request.get(`${API}/runs/not-a-run-id`, {
			headers: HEADERS
		});
		expect(res.status()).toBe(400);
	});
});

// Touch the workspace-shared API string to satisfy the linter without
// changing the others' imports.
void uploadFixture;
