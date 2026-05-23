import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const STORAGE_KEY = 'disag.client_id';
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

describe('getClientId', () => {
	beforeEach(() => {
		localStorage.clear();
		// Reset module state so the in-file `cached` singleton starts
		// fresh between tests.
		vi.resetModules();
	});

	afterEach(() => {
		localStorage.clear();
	});

	it('mints a fresh UUID and persists it on first call', async () => {
		const { getClientId } = await import('./clientId');

		const id = getClientId();
		expect(id).toMatch(UUID_RE);
		expect(localStorage.getItem(STORAGE_KEY)).toBe(id);
	});

	it('returns the same value across calls in the same module load (caches)', async () => {
		const { getClientId } = await import('./clientId');

		const a = getClientId();
		const b = getClientId();
		expect(a).toBe(b);
	});

	it('reuses an existing valid UUID from localStorage', async () => {
		const fixed = '12345678-1234-4234-8234-123456789abc';
		localStorage.setItem(STORAGE_KEY, fixed);
		const { getClientId } = await import('./clientId');

		expect(getClientId()).toBe(fixed);
	});

	it('discards garbage from localStorage and mints a fresh UUID', async () => {
		localStorage.setItem(STORAGE_KEY, 'not-a-uuid');
		const { getClientId } = await import('./clientId');

		const id = getClientId();
		expect(id).not.toBe('not-a-uuid');
		expect(id).toMatch(UUID_RE);
		expect(localStorage.getItem(STORAGE_KEY)).toBe(id);
	});

	it('falls back to a one-shot UUID when localStorage is undefined (SSR)', async () => {
		// SvelteKit static mode renders the landing page on the server
		// first, then hydrates. In the server pass `localStorage` is
		// undefined and we should mint a throwaway without exploding.
		// Use Reflect.deleteProperty so jsdom's window keeps its other
		// fields intact.
		const orig = globalThis.localStorage;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		(globalThis as any).localStorage = undefined;
		try {
			const { getClientId } = await import('./clientId');
			const id = getClientId();
			expect(id).toMatch(UUID_RE);
		} finally {
			globalThis.localStorage = orig;
		}
	});
});

describe('resetClientId', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.resetModules();
	});

	it('clears localStorage and forces the next getClientId to mint a fresh value', async () => {
		const { getClientId, resetClientId } = await import('./clientId');

		const first = getClientId();
		expect(localStorage.getItem(STORAGE_KEY)).toBe(first);

		resetClientId();
		expect(localStorage.getItem(STORAGE_KEY)).toBeNull();

		const second = getClientId();
		expect(second).not.toBe(first);
		expect(second).toMatch(UUID_RE);
	});
});
