import { error } from '@sveltejs/kit';
import { docLinks, docSlugs, getDoc } from '$lib/server/docs';
import type { EntryGenerator, PageServerLoad } from './$types';

// Prerendered at build time — the markdown is converted once and shipped as
// static HTML, so `marked` never reaches the client and there is no server at
// runtime (adapter-static).
export const prerender = true;

export const entries: EntryGenerator = () => docSlugs.map((slug) => ({ slug }));

export const load: PageServerLoad = ({ params }) => {
	const doc = getDoc(params.slug);
	if (!doc) throw error(404, `No docs page named "${params.slug}".`);
	return { doc, nav: docLinks };
};
