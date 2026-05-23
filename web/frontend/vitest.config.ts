import { defineConfig } from 'vitest/config';

// Unit tests for src/lib/. Separate from the Playwright e2e suites
// in e2e/ — Vitest covers per-module logic (UUID minting, header
// shape, env-var defaults) without spinning up a browser.
export default defineConfig({
	test: {
		environment: 'jsdom',
		include: ['src/**/*.test.ts'],
		// Auto-reset between tests so vi.stubEnv / vi.stubGlobal /
		// vi.spyOn don't leak. vi.resetModules() still has to be
		// called manually before a dynamic import — the env-var
		// override tests rely on re-evaluating `import.meta.env`.
		restoreMocks: true,
		unstubEnvs: true,
		unstubGlobals: true
	}
});
