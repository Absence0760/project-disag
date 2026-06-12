// Canonical order, nav labels, and one-line blurbs for the docs section.
// Client-safe (plain strings, no markdown) so both the docs layout's side
// panel and the overview's "Go deeper" grid can import it directly; the
// build-time renderer in $lib/server/docs.ts reuses this list for slug order
// so the three never drift. Adding a doc here (plus its docs/<slug>.md and a
// raw import in docs.ts) is all it takes to surface a new page everywhere.

export type DocGroup = 'Get started' | 'How it works' | 'Reference' | 'Help';

export type DocPage = { slug: string; label: string; blurb: string; group: DocGroup };

// The side panel renders these grouped by `group`, in first-appearance order,
// so keep entries that share a group together here.
export const DOC_PAGES: DocPage[] = [
	{
		slug: 'problem',
		label: 'The problem',
		blurb: 'The domain context, with worked examples for both tools.',
		group: 'Get started'
	},
	{
		slug: 'usage',
		label: 'Usage & quickstart',
		blurb: 'Run the desktop GUI, the CLI, and the web tool — every flag explained.',
		group: 'Get started'
	},
	{
		slug: 'algorithm',
		label: 'Disaggregation algorithm',
		blurb: "The core formula and every method's behaviour, step by step.",
		group: 'How it works'
	},
	{
		slug: 'exceed',
		label: 'Exceedance analysis',
		blurb: 'The flow-frequency algorithm, seasonal grouping, and matching logic.',
		group: 'How it works'
	},
	{
		slug: 'method5',
		label: 'Method 5 deep-dive',
		blurb: 'The exceedance-matched cross-river donor — what it solves and how.',
		group: 'How it works'
	},
	{
		slug: 'converter',
		label: 'Format converter',
		blurb: 'Turn a Pitman .ANS monthly file into the .MON layout Disag reads.',
		group: 'Reference'
	},
	{
		slug: 'file-formats',
		label: 'File formats',
		blurb: 'The complete .mon / .day / .rep on-disk spec.',
		group: 'Reference'
	},
	{
		slug: 'glossary',
		label: 'Glossary',
		blurb: 'Plain-language definitions of the hydrology terms used throughout.',
		group: 'Reference'
	},
	{
		slug: 'faq',
		label: 'FAQ & troubleshooting',
		blurb: 'Common errors and how to fix them.',
		group: 'Help'
	},
	{
		slug: 'building',
		label: 'Building executables',
		blurb: 'Per-OS PyInstaller build guide for the standalone CLI binaries.',
		group: 'Help'
	}
];
