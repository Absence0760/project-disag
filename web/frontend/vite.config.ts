import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// Dev proxy: forward /api/* to the local Lambda shim on :8000 so the
// SPA can use the same `/api/...` paths it uses in production. The
// shim's handler.py strips the `/api` prefix; that mirrors what
// CloudFront's `/api/*` behaviour does at the edge.
//
// `rewrite` is intentionally a no-op (`path => path`) — we forward the
// `/api` prefix and let the backend handler do the strip, so dev and
// prod request shapes are identical.
//
// Preview proxy: `pnpm preview` serves the production build, which the
// integration Playwright project uses alongside local_server.py on
// port 8765 (see web/frontend/playwright.config.ts). Same proxy shape
// as the dev server, just pointed at the integration backend.
export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		// The docs pages import the repo's docs/*.md as `?raw` (see
		// src/lib/server/docs.ts), which live two levels above this
		// frontend package — allow the dev server to read them.
		fs: {
			allow: ['../..']
		},
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true
			}
		}
	},
	preview: {
		port: 4173,
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:8765',
				changeOrigin: true
			}
		}
	}
});
