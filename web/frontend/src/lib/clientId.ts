/**
 * Anonymous browser session ID.
 *
 * The backend has no user accounts; every API call carries an
 * X-Client-Id header derived from this UUID so the Lambda can scope
 * S3 prefixes (inputs/<client_id>/..., runs/<tool>/<client_id>/...)
 * to each browser. Clearing storage = losing history; intentional
 * trade-off for not requiring sign-up.
 *
 * Lives in localStorage (persists across tabs and reloads) under the
 * key `disag.client_id`. UUID v4 via crypto.randomUUID() — present in
 * every modern browser and node >= 14.
 */

const STORAGE_KEY = 'disag.client_id';

let cached: string | null = null;

export function getClientId(): string {
	if (cached) return cached;

	// SSR / Node — generate a throwaway. In SvelteKit static mode the
	// landing page renders on the server first, then hydrates; the
	// hydration pass re-reads localStorage and replaces this value.
	if (typeof localStorage === 'undefined') {
		return crypto.randomUUID();
	}

	const existing = localStorage.getItem(STORAGE_KEY);
	if (existing && isUuidV4(existing)) {
		cached = existing;
		return existing;
	}

	const fresh = crypto.randomUUID();
	localStorage.setItem(STORAGE_KEY, fresh);
	cached = fresh;
	return fresh;
}

/**
 * Wipe the local client ID — used by the "Forget my history" affordance
 * if/when we add one. Next API call will mint and store a new UUID.
 */
export function resetClientId(): void {
	cached = null;
	if (typeof localStorage !== 'undefined') {
		localStorage.removeItem(STORAGE_KEY);
	}
}

function isUuidV4(s: string): boolean {
	return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);
}
