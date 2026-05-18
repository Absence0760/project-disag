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
export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true
			}
		}
	}
});
