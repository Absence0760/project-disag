import { beforeEach, describe, expect, it, vi } from 'vitest';

function mockFetchOk<T>(body: T) {
	return vi.fn().mockResolvedValue({
		ok: true,
		status: 200,
		json: async () => body,
		text: async () => JSON.stringify(body)
	});
}

function mockFetchErr(status: number, body: string) {
	return vi.fn().mockResolvedValue({
		ok: false,
		status,
		statusText: 'Bad Request',
		text: async () => body
	});
}

describe('api.ts: API_BASE', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.resetModules();
	});

	it('defaults to /api when VITE_API_BASE is unset', async () => {
		const fetchSpy = mockFetchOk([]);
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await api.listRuns();

		expect(fetchSpy).toHaveBeenCalledOnce();
		expect(fetchSpy.mock.calls[0][0]).toBe('/api/runs');
	});

	it('honours VITE_API_BASE when set', async () => {
		vi.stubEnv('VITE_API_BASE', 'https://api.example.com');
		const fetchSpy = mockFetchOk([]);
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await api.listRuns();

		expect(fetchSpy.mock.calls[0][0]).toBe('https://api.example.com/runs');
	});
});

describe('api.ts: request shape', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.resetModules();
	});

	it('sends x-client-id on every request', async () => {
		const fetchSpy = mockFetchOk([]);
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await api.listRuns();

		const init = fetchSpy.mock.calls[0][1];
		const headers = init.headers as Record<string, string>;
		expect(headers['x-client-id']).toMatch(
			/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
		);
	});

	it('sends content-type: application/json on every request', async () => {
		const fetchSpy = mockFetchOk({});
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await api.runDisag({ method: 0, monthly_key: 'inputs/x/y/z.mon' });

		const init = fetchSpy.mock.calls[0][1];
		const headers = init.headers as Record<string, string>;
		expect(headers['content-type']).toBe('application/json');
	});

	it('reuses the same client id across consecutive calls', async () => {
		const fetchSpy = mockFetchOk([]);
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await api.listRuns();
		await api.listRuns();

		const a = (fetchSpy.mock.calls[0][1].headers as Record<string, string>)['x-client-id'];
		const b = (fetchSpy.mock.calls[1][1].headers as Record<string, string>)['x-client-id'];
		expect(a).toBe(b);
	});

	it('sends POST bodies for the action routes', async () => {
		const fetchSpy = mockFetchOk({});
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await api.runConvert({ ans_key: 'inputs/x/y/z.ans' });

		const init = fetchSpy.mock.calls[0][1];
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({ ans_key: 'inputs/x/y/z.ans' });
		expect(fetchSpy.mock.calls[0][0]).toBe('/api/convert');
	});

	it('url-encodes the run id segment in GET /runs/{id}', async () => {
		const fetchSpy = mockFetchOk({});
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await api.getRun('weird id/with slashes');

		expect(fetchSpy.mock.calls[0][0]).toBe('/api/runs/weird%20id%2Fwith%20slashes');
	});
});

describe('api.ts: error handling', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.resetModules();
	});

	it('throws with status + body on non-2xx', async () => {
		const fetchSpy = mockFetchErr(403, '{"error":"does not belong"}');
		vi.stubGlobal('fetch', fetchSpy);

		const api = await import('./api');
		await expect(api.listRuns()).rejects.toThrow(/403.*does not belong/);
	});
});
