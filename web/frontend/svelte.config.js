import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// adapter-static + SPA fallback: ship to S3 + CloudFront, all
		// routing happens client-side. No SSR — the backend is Lambda
		// behind API Gateway, hit from the browser.
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html',
			precompress: true,
			strict: true
		})
	}
};

export default config;
