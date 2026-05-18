import type { DisagRequest, ExceedRequest, RunResult, RunSummary, UploadTarget } from './types';
import { getClientId } from './clientId';

// Default to `/api` so production hits CloudFront's `/api/*` behaviour
// (forwarded to API Gateway → Lambda). In dev, vite.config.ts proxies
// `/api` to the local backend on port 8000, so the same paths work
// without a per-environment override. VITE_API_BASE in `.env` can still
// override (e.g. point at a deployed API Gateway URL directly).
const API_BASE = import.meta.env.VITE_API_BASE ?? '/api';

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`${API_BASE}${path}`, {
		...init,
		headers: {
			'content-type': 'application/json',
			'x-client-id': getClientId(),
			...(init?.headers ?? {})
		}
	});
	if (!res.ok) {
		const body = await res.text();
		throw new Error(`${res.status} ${res.statusText}: ${body}`);
	}
	return res.json() as Promise<T>;
}

export async function requestUpload(filename: string): Promise<UploadTarget> {
	return jsonFetch<UploadTarget>('/upload', {
		method: 'POST',
		body: JSON.stringify({ filename })
	});
}

/**
 * Upload a file using the presigned S3 POST policy returned by
 * /upload. The order in the FormData matters: every signed `field`
 * must precede the file (S3's policy engine reads top-down). If the
 * file exceeds `target.max_bytes`, S3 rejects the POST server-side —
 * we still surface a friendly client-side preflight error to avoid
 * a confusing 403 from S3.
 */
export async function putToS3(target: UploadTarget, file: File): Promise<void> {
	if (file.size > target.max_bytes) {
		const limitMib = (target.max_bytes / (1024 * 1024)).toFixed(0);
		throw new Error(`File too large (${file.size} bytes; limit ${limitMib} MiB).`);
	}
	const form = new FormData();
	for (const [k, v] of Object.entries(target.fields)) {
		form.append(k, v);
	}
	form.append('file', file);
	const res = await fetch(target.url, { method: 'POST', body: form });
	if (!res.ok) {
		throw new Error(`S3 upload failed: ${res.status} ${res.statusText}`);
	}
}

export async function runDisag(req: DisagRequest): Promise<RunResult> {
	return jsonFetch<RunResult>('/disag', { method: 'POST', body: JSON.stringify(req) });
}

export async function runExceed(req: ExceedRequest): Promise<RunResult> {
	return jsonFetch<RunResult>('/exceed', { method: 'POST', body: JSON.stringify(req) });
}

export async function listRuns(): Promise<RunSummary[]> {
	return jsonFetch<RunSummary[]>('/runs');
}

export async function getRun(runId: string): Promise<RunResult> {
	return jsonFetch<RunResult>(`/runs/${encodeURIComponent(runId)}`);
}
