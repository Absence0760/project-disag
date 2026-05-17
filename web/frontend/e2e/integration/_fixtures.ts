/**
 * Helpers for the integration specs. The Playwright config boots
 * local_server.py on :8765 with LOCAL_S3=1, so requests go straight to
 * the real handler.py over HTTP — no AWS, no mocks.
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { APIRequestContext } from '@playwright/test';
import { expect } from '@playwright/test';

export const API = 'http://127.0.0.1:8765';

// Repo root from web/frontend/e2e/integration/ is four up.
const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = join(HERE, '..', '..', '..', '..');

export function fixturePath(demo: string, name: string): string {
	return join(REPO_ROOT, 'examples', demo, 'data', name);
}

export async function uploadFixture(
	request: APIRequestContext,
	demo: string,
	filename: string
): Promise<string> {
	const presign = await request.post(`${API}/upload`, { data: { filename } });
	expect(presign.ok(), `presign /upload for ${filename}`).toBeTruthy();
	const { key, url } = await presign.json();

	const body = readFileSync(fixturePath(demo, filename));
	const put = await request.fetch(url, { method: 'PUT', data: body });
	expect(put.ok(), `PUT ${url}`).toBeTruthy();

	return key as string;
}

export async function fetchText(request: APIRequestContext, url: string): Promise<string> {
	const res = await request.get(url);
	expect(res.ok(), `GET ${url}`).toBeTruthy();
	return res.text();
}

export interface RunResult {
	run_id: string;
	tool: 'disag' | 'exceed';
	output_key?: string;
	report_key: string;
	output_url?: string;
	report_url: string;
}

export async function runDisag(
	request: APIRequestContext,
	body: Record<string, unknown>
): Promise<RunResult> {
	const res = await request.post(`${API}/disag`, { data: body });
	expect(res.ok(), `POST /disag (${JSON.stringify(body)})`).toBeTruthy();
	return res.json();
}

export async function runExceed(
	request: APIRequestContext,
	body: Record<string, unknown>
): Promise<RunResult> {
	const res = await request.post(`${API}/exceed`, { data: body });
	expect(res.ok(), `POST /exceed (${JSON.stringify(body)})`).toBeTruthy();
	return res.json();
}
