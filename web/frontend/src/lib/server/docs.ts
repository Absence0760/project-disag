// Build-time docs renderer. Lives under $lib/server so `marked` and the
// raw markdown only ever run during prerender — none of this reaches the
// client bundle. The repo's docs/*.md files are imported as raw strings
// (the paths climb out of web/frontend to the repo root) and turned into
// HTML once, at module load. Consumed by routes/docs/[slug]/+page.server.ts.

import { marked } from 'marked';
import { DOC_PAGES } from '$lib/docMeta';

// Raw markdown, imported straight from the repo's docs/ directory. Vite's
// `?raw` query returns the file contents as a string at build time.
import problem from '../../../../../docs/problem.md?raw';
import usage from '../../../../../docs/usage.md?raw';
import algorithm from '../../../../../docs/algorithm.md?raw';
import exceed from '../../../../../docs/exceed.md?raw';
import method5 from '../../../../../docs/method5.md?raw';
import converter from '../../../../../docs/converter.md?raw';
import fileFormats from '../../../../../docs/file-formats.md?raw';
import glossary from '../../../../../docs/glossary.md?raw';
import faq from '../../../../../docs/faq.md?raw';
import building from '../../../../../docs/building.md?raw';

const GITHUB_BASE = 'https://github.com/Absence0760/project-disag';

const RAW: Record<string, string> = {
	problem,
	usage,
	algorithm,
	exceed,
	method5,
	converter,
	'file-formats': fileFormats,
	glossary,
	faq,
	building
};

// Order and membership come from the shared DOC_PAGES list so the rendered
// pages and the layout's side panel stay in lockstep.
const SOURCES: Array<{ slug: string; source: string }> = DOC_PAGES.map(({ slug }) => ({
	slug,
	source: RAW[slug]
}));

const SLUGS = new Set(SOURCES.map((d) => d.slug));

// Map a markdown filename (as written inside the docs) to its slug, derived
// from the shared page list so a new doc is linkable the moment it's added.
const FILE_TO_SLUG: Record<string, string> = Object.fromEntries(
	DOC_PAGES.map(({ slug }) => [`${slug}.md`, slug])
);

// Minimal POSIX-ish path normaliser — enough to resolve the `../` links the
// docs use (e.g. `../CLAUDE.md`, `../examples/method5_demo/`) relative to the
// docs/ directory so they become correct repo-root paths for GitHub.
function normalize(path: string): string {
	const out: string[] = [];
	for (const part of path.split('/')) {
		if (part === '' || part === '.') continue;
		if (part === '..') out.pop();
		else out.push(part);
	}
	return out.join('/');
}

// Rewrite a link href written for the on-disk docs into one that works on the
// website: sibling .md docs become /docs/<slug>; everything else relative
// resolves against the repo and points at GitHub. Absolute site paths (`/run`,
// `/docs#methods`), full URLs, and in-page anchors pass through untouched.
function rewriteHref(href: string): string {
	if (
		!href ||
		href.startsWith('http://') ||
		href.startsWith('https://') ||
		href.startsWith('#') ||
		href.startsWith('/')
	) {
		return href;
	}

	const hashAt = href.indexOf('#');
	const path = hashAt === -1 ? href : href.slice(0, hashAt);
	const hash = hashAt === -1 ? '' : href.slice(hashAt);

	const file = path.split('/').pop() ?? '';
	if (file in FILE_TO_SLUG && !path.includes('..')) {
		return `/docs/${FILE_TO_SLUG[file]}${hash}`;
	}

	// Anything else relative: resolve from docs/ and link to the repo.
	const resolved = normalize(`docs/${path}`);
	const kind = path.endsWith('/') ? 'tree' : 'blob';
	return `${GITHUB_BASE}/${kind}/main/${resolved}${hash}`;
}

// GitHub-style heading slugs, so the in-page tables of contents some docs
// carry (e.g. building.md) resolve to real element ids. Reset before each
// parse — see DOCS below; parsing is synchronous so there's no interleaving.
let headingSlugs = new Map<string, number>();

function slugify(text: string): string {
	const base = text
		.toLowerCase()
		.replace(/<[^>]+>/g, '')
		.replace(/[^\w\s-]/g, '')
		.trim()
		.replace(/\s+/g, '-')
		.replace(/-+/g, '-')
		.replace(/^-|-$/g, '');
	const seen = headingSlugs.get(base) ?? 0;
	headingSlugs.set(base, seen + 1);
	return seen === 0 ? base : `${base}-${seen}`;
}

// Rewrite link/image targets, add heading ids, and harden outbound links.
// Registered once, globally — marked applies it on every parse below.
marked.use({
	walkTokens(token) {
		if (token.type === 'link' || token.type === 'image') {
			token.href = rewriteHref(token.href);
		}
	},
	renderer: {
		heading(token) {
			const text = this.parser.parseInline(token.tokens);
			const id = slugify(token.text);
			return `<h${token.depth} id="${id}">${text}</h${token.depth}>\n`;
		},
		link({ href, title, text }) {
			const external = href.startsWith('http');
			const attrs = external ? ' rel="noopener" target="_blank"' : '';
			const t = title ? ` title="${title}"` : '';
			return `<a href="${href}"${t}${attrs}>${text}</a>`;
		}
	}
});

// Pull the first `# Heading` as the page title, and strip it from the body so
// the route can render the title in its own header without duplication.
function splitTitle(md: string): { title: string; body: string } {
	const lines = md.split('\n');
	const i = lines.findIndex((l) => l.startsWith('# '));
	if (i === -1) return { title: 'Documentation', body: md };
	const title = lines[i].replace(/^#\s+/, '').trim();
	const body = [...lines.slice(0, i), ...lines.slice(i + 1)].join('\n');
	return { title, body };
}

// Plain-text version of an inline-markdown heading, for <title>/sidebar use.
function plainText(md: string): string {
	return md
		.replace(/`([^`]+)`/g, '$1')
		.replace(/\*\*([^*]+)\*\*/g, '$1')
		.replace(/\*([^*]+)\*/g, '$1')
		.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
		.trim();
}

export type Doc = { slug: string; title: string; html: string };

const DOCS: Doc[] = SOURCES.map(({ slug, source }) => {
	const { title, body } = splitTitle(source);
	headingSlugs = new Map(); // fresh slug namespace per document
	return {
		slug,
		title: plainText(title),
		html: marked.parse(body) as string
	};
});

export const docSlugs: string[] = SOURCES.map((d) => d.slug);

export function getDoc(slug: string): Doc | undefined {
	if (!SLUGS.has(slug)) return undefined;
	return DOCS.find((d) => d.slug === slug);
}
