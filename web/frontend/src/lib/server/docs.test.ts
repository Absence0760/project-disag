import { describe, expect, it } from 'vitest';
import { marked } from 'marked';

// Importing the module registers the custom heading/link renderers on the
// shared `marked` instance (and renders the real docs corpus as a side
// effect, so a doc that breaks the pipeline fails this suite at import).
import { docSlugs, getDoc } from './docs';

// Parse a snippet through the same renderer the docs pages use, and hand
// back a DOM view of it (jsdom) for attribute-level assertions.
function render(md: string): { html: string; root: HTMLElement } {
	const html = marked.parse(md) as string;
	const root = document.createElement('div');
	root.innerHTML = html;
	return { html, root };
}

describe('docs.ts: well-formed input renders as before', () => {
	it('pins the heading shape', () => {
		const { html } = render('## Alpha bravo charlie');
		expect(html).toBe('<h2 id="alpha-bravo-charlie">Alpha bravo charlie</h2>\n');
	});

	it('pins the external link shape (rel/target hardening)', () => {
		const { html } = render('[repo](https://example.com/x)');
		expect(html).toBe(
			'<p><a href="https://example.com/x" rel="noopener" target="_blank">repo</a></p>\n'
		);
	});

	it('pins the titled link shape', () => {
		const { html } = render('[repo](https://example.com/x "Site docs")');
		expect(html).toBe(
			'<p><a href="https://example.com/x" title="Site docs" rel="noopener" target="_blank">repo</a></p>\n'
		);
	});

	it('pins the internal doc link shape (no rel/target)', () => {
		const { html } = render('[the problem](problem.md)');
		expect(html).toBe('<p><a href="/docs/problem">the problem</a></p>\n');
	});

	it('still renders the whole docs corpus', () => {
		for (const slug of docSlugs) {
			const doc = getDoc(slug);
			expect(doc, slug).toBeDefined();
			expect(doc!.html, slug).toContain('<');
		}
	});
});

describe('docs.ts: attribute escaping', () => {
	it('a double quote in a heading cannot break out of the id attribute', () => {
		const { html, root } = render('# Delta "echo" foxtrot');
		const h1 = root.querySelector('h1')!;
		// slugify strips the quotes; escapeAttr guards whatever remains.
		expect(h1.id).toBe('delta-echo-foxtrot');
		expect(html).toBe('<h1 id="delta-echo-foxtrot">Delta &quot;echo&quot; foxtrot</h1>\n');
	});

	it('a double quote in a link href cannot close the attribute', () => {
		const { html, root } = render('[x](https://example.com/x"y)');
		const a = root.querySelector('a')!;
		expect(html).toContain('href="https://example.com/x&quot;y"');
		expect(a.getAttribute('href')).toBe('https://example.com/x"y');
		expect(a.attributes).toHaveLength(3); // href, rel, target — nothing injected
	});

	it('a double quote in a link title cannot inject attributes', () => {
		const { root } = render(`[x](https://example.com/x '" onmouseover="alert(1)')`);
		const a = root.querySelector('a')!;
		expect(a.getAttribute('title')).toBe('" onmouseover="alert(1)');
		expect(a.hasAttribute('onmouseover')).toBe(false);
	});
});
