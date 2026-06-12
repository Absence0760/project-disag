// Canonical order + nav labels for the docs section. Client-safe (plain
// strings, no markdown) so the docs layout's side panel can import it
// directly; the build-time renderer in $lib/server/docs.ts reuses this list
// for slug order so the two never drift.

export type DocPage = { slug: string; label: string };

export const DOC_PAGES: DocPage[] = [
	{ slug: 'problem', label: 'The problem' },
	{ slug: 'algorithm', label: 'Disaggregation algorithm' },
	{ slug: 'exceed', label: 'Exceedance analysis' },
	{ slug: 'method5', label: 'Method 5 deep-dive' },
	{ slug: 'file-formats', label: 'File formats' },
	{ slug: 'building', label: 'Building executables' }
];
