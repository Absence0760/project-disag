import { randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { API, fetchText, fixturePath } from './_fixtures';

// Local client id so this spec's runs don't pollute disag.spec's
// runs.every(r => r.tool === 'disag') listing assertion. (Integration
// specs all share workers=1 + a single .local-s3 dir; the alphabetic
// run order means convert.spec lands first.)
const CLIENT_ID = randomUUID();
const HEADERS = { 'x-client-id': CLIENT_ID };

async function uploadAns(
	request: import('@playwright/test').APIRequestContext,
	filename: string
): Promise<string> {
	const presign = await request.post(`${API}/upload`, {
		data: { filename },
		headers: HEADERS
	});
	expect(presign.ok(), `presign /upload for ${filename}`).toBeTruthy();
	const { key, url, fields } = await presign.json();
	const buf = readFileSync(fixturePath('convert_demo', filename));
	const post = await request.post(url, {
		multipart: {
			...fields,
			file: { name: filename, mimeType: 'application/octet-stream', buffer: buf }
		}
	});
	expect(post.ok(), `POST ${url}`).toBeTruthy();
	return key as string;
}

/**
 * End-to-end round-trip of the /convert endpoint against the real
 * handler.py + local_server.py stack the integration suite already
 * boots (LOCAL_S3=1, no AWS). Uploads the synthesized .ANS fixture
 * under examples/convert_demo/data/, asks the backend to convert it,
 * and reads the returned .mon back.
 */

test.describe('@integration convert', () => {
	test('round-trips a sample monthly file through /convert', async ({ request }) => {
		const ansKey = await uploadAns(request, 'SAMPLE.ANS');

		const res = await request.post(`${API}/convert`, {
			data: { ans_key: ansKey },
			headers: HEADERS
		});
		expect(res.ok(), 'POST /convert').toBeTruthy();
		const result = await res.json();

		expect(result.tool).toBe('convert');
		expect(result.output_url, 'output_url present').toBeTruthy();
		expect(result.output_key, 'output_key ends in .mon').toMatch(/\.mon$/);

		const out = await fetchText(request, result.output_url);
		// The fixture is three hydro years; output must echo them.
		expect(out).toContain('Source        : converted from SAMPLE.ANS');
		expect(out).toMatch(/^\s*1990\s/m);
		expect(out).toMatch(/^\s*1991\s/m);
		expect(out).toMatch(/^\s*1992\s/m);
		// The flood-year row's collided columns must be split correctly.
		expect(out).toMatch(/1991.*9999\.990.*14639\.120.*13670\.740/);

		const report = await fetchText(request, result.report_url);
		expect(report).toContain('Rows written: 3');
		expect(report).toContain('Skipped     : 2 non-data line(s)');
	});

	test('rejects a key from another client with 403', async ({ request }) => {
		const res = await request.post(`${API}/convert`, {
			data: { ans_key: 'inputs/some-other-client/whatever/foo.ans' },
			headers: HEADERS
		});
		expect(res.status()).toBe(403);
	});

	test('400 when ans_key is missing', async ({ request }) => {
		const res = await request.post(`${API}/convert`, {
			data: {},
			headers: HEADERS
		});
		expect(res.status()).toBe(400);
	});
});
