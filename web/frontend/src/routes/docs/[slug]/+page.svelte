<script lang="ts">
	import { page } from '$app/state';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const doc = $derived(data.doc);
	const nav = $derived(data.nav);
</script>

<svelte:head>
	<title>{doc.title} · Disag-MD docs</title>
</svelte:head>

<nav class="crumbs" aria-label="Breadcrumb">
	<a href="/docs">Docs</a>
	<span aria-hidden="true">/</span>
	<span aria-current="page">{doc.title}</span>
</nav>

<div class="layout">
	<aside class="sidebar" aria-label="Documentation pages">
		<a class="side-overview" href="/docs">← Overview</a>
		<ul>
			{#each nav as item (item.slug)}
				<li>
					<a
						href={`/docs/${item.slug}`}
						aria-current={page.params.slug === item.slug ? 'page' : undefined}
						class:active={page.params.slug === item.slug}
					>
						{item.title}
					</a>
				</li>
			{/each}
		</ul>
	</aside>

	<article>
		<h1 class="doc-title">{doc.title}</h1>
		<!-- doc.html is built at prerender time from the repo's own trusted
		     docs/*.md files (see $lib/server/docs.ts) — no user input flows here. -->
		<div class="prose">
			{@html doc.html}
		</div>
	</article>
</div>

<style>
	.crumbs {
		display: flex;
		gap: var(--space-2);
		align-items: center;
		font-size: 0.85rem;
		color: var(--text-subtle);
		margin-bottom: var(--space-4);
	}
	.crumbs span[aria-current] {
		color: var(--text-muted);
	}

	.layout {
		display: grid;
		grid-template-columns: 220px minmax(0, 1fr);
		gap: var(--space-6);
		align-items: start;
	}

	.sidebar {
		position: sticky;
		top: 90px;
		border-right: 1px solid var(--border);
		padding-right: var(--space-4);
	}
	.side-overview {
		display: inline-block;
		font-size: 0.85rem;
		color: var(--text-muted);
		margin-bottom: var(--space-3);
		font-weight: 500;
	}
	.sidebar ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.sidebar a {
		display: block;
		padding: 0.4rem 0.6rem;
		border-radius: var(--radius-sm);
		font-size: 0.9rem;
		color: var(--text-muted);
		line-height: 1.3;
	}
	.sidebar a:hover {
		background: var(--surface-2);
		color: var(--text);
		text-decoration: none;
	}
	.sidebar a.active {
		background: var(--accent-soft);
		color: var(--accent);
		font-weight: 600;
	}

	.layout > article {
		min-width: 0;
	}
	.doc-title {
		font-size: clamp(1.7rem, 2.2vw, 2.1rem);
		margin: 0 0 var(--space-4);
		color: var(--text);
	}

	/* Prose — styling for the marked-generated HTML. Uses the shared design
	   tokens so it tracks light/dark with the rest of the site. */
	.prose {
		color: var(--text-muted);
		font-size: 1rem;
		line-height: 1.65;
	}
	.prose :global(h2) {
		font-size: 1.4rem;
		margin: var(--space-6) 0 var(--space-3);
		padding-bottom: var(--space-2);
		border-bottom: 1px solid var(--border);
		color: var(--text);
	}
	.prose :global(h3) {
		font-size: 1.12rem;
		margin: var(--space-5) 0 var(--space-2);
		color: var(--text);
	}
	.prose :global(h4) {
		font-size: 1rem;
		margin: var(--space-4) 0 var(--space-2);
		color: var(--text);
	}
	.prose :global(p),
	.prose :global(li) {
		color: var(--text-muted);
	}
	.prose :global(a) {
		color: var(--accent);
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.prose :global(ul),
	.prose :global(ol) {
		padding-left: 1.4rem;
	}
	.prose :global(li) {
		margin: 0.25rem 0;
	}
	.prose :global(strong) {
		color: var(--text);
	}
	.prose :global(hr) {
		border: none;
		border-top: 1px solid var(--border);
		margin: var(--space-6) 0;
	}
	.prose :global(blockquote) {
		margin: var(--space-4) 0;
		padding: var(--space-1) var(--space-4);
		border-left: 3px solid var(--accent);
		background: var(--surface-2);
		border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
		color: var(--text-muted);
	}

	/* Inline code + fenced blocks. The shared `code` style in app.css covers
	   inline; here we handle the <pre> wrapper for multi-line blocks. */
	.prose :global(code) {
		font-family: var(--font-mono);
		font-size: 0.88em;
		background: var(--surface-2);
		padding: 0.1em 0.4em;
		border-radius: var(--radius-sm);
	}
	.prose :global(pre) {
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: var(--space-4);
		overflow-x: auto;
		margin: var(--space-4) 0;
		line-height: 1.5;
	}
	.prose :global(pre code) {
		background: none;
		padding: 0;
		font-size: 0.85rem;
		color: var(--text);
	}

	/* Tables — the docs lean on these heavily (method matrices, format specs). */
	.prose :global(table) {
		width: 100%;
		border-collapse: collapse;
		margin: var(--space-4) 0;
		font-size: 0.92rem;
		display: block;
		overflow-x: auto;
	}
	.prose :global(th),
	.prose :global(td) {
		text-align: left;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--border);
		vertical-align: top;
	}
	.prose :global(thead th) {
		background: var(--surface-2);
		color: var(--text);
		font-weight: 600;
	}
	.prose :global(tbody tr:nth-child(even)) {
		background: color-mix(in srgb, var(--surface-2) 45%, transparent);
	}

	.prose :global(img) {
		max-width: 100%;
		height: auto;
	}

	@media (max-width: 720px) {
		.layout {
			grid-template-columns: 1fr;
			gap: var(--space-4);
		}
		.sidebar {
			position: static;
			border-right: none;
			border-bottom: 1px solid var(--border);
			padding-right: 0;
			padding-bottom: var(--space-3);
		}
		.sidebar ul {
			flex-direction: row;
			flex-wrap: wrap;
		}
	}
</style>
