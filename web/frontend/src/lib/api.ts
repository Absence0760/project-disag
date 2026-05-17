import type { DisagRequest, ExceedRequest, RunResult, RunSummary, UploadTarget } from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`${API_BASE}${path}`, {
		...init,
		headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) }
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

export async function putToS3(target: UploadTarget, file: File): Promise<void> {
	const res = await fetch(target.url, { method: 'PUT', body: file });
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
