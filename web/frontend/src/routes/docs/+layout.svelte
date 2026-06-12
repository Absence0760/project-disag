<script lang="ts">
	import { page } from '$app/state';
	import { DOC_PAGES } from '$lib/docMeta';

	let { children } = $props();

	const isActive = (href: string) => page.url.pathname === href;
</script>

<div class="docs-shell">
	<aside class="docs-side" aria-label="Documentation">
		<p class="side-title">Documentation</p>
		<nav>
			<a
				href="/docs"
				class:active={isActive('/docs')}
				aria-current={isActive('/docs') ? 'page' : undefined}
			>
				Overview
			</a>
			<span class="side-sep">Reference</span>
			{#each DOC_PAGES as doc (doc.slug)}
				<a
					href={`/docs/${doc.slug}`}
					class:active={isActive(`/docs/${doc.slug}`)}
					aria-current={isActive(`/docs/${doc.slug}`) ? 'page' : undefined}
				>
					{doc.label}
				</a>
			{/each}
		</nav>
	</aside>

	<div class="docs-main">
		{@render children()}
	</div>
</div>

<style>
	.docs-shell {
		display: grid;
		grid-template-columns: 200px minmax(0, 1fr);
		gap: var(--space-6);
		align-items: start;
	}

	.docs-side {
		position: sticky;
		top: 84px;
	}

	.side-title {
		margin: 0 0 var(--space-2);
		font-size: 0.74rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.09em;
		color: var(--text-subtle);
	}

	.docs-side nav {
		display: flex;
		flex-direction: column;
		gap: 2px;
		border-left: 1px solid var(--border);
		padding-left: var(--space-2);
	}

	.docs-side a {
		display: block;
		padding: 0.4rem 0.6rem;
		border-radius: var(--radius-sm);
		font-size: 0.9rem;
		font-weight: 500;
		color: var(--text-muted);
		line-height: 1.3;
		border-left: 2px solid transparent;
		margin-left: -2px;
	}
	.docs-side a:hover {
		background: var(--surface-2);
		color: var(--text);
		text-decoration: none;
	}
	.docs-side a.active {
		color: var(--accent);
		border-left-color: var(--accent);
		font-weight: 600;
	}

	.side-sep {
		margin: var(--space-3) 0 var(--space-1) var(--space-1);
		font-size: 0.68rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-subtle);
	}

	.docs-main {
		min-width: 0;
	}

	@media (max-width: 760px) {
		.docs-shell {
			grid-template-columns: 1fr;
			gap: var(--space-4);
		}
		.docs-side {
			position: static;
		}
		.docs-side nav {
			flex-direction: row;
			flex-wrap: wrap;
			border-left: none;
			border-bottom: 1px solid var(--border);
			padding-left: 0;
			padding-bottom: var(--space-3);
			gap: 4px;
		}
		.docs-side a {
			border-left: none;
			margin-left: 0;
			background: var(--surface-2);
		}
		.docs-side a.active {
			background: var(--accent-soft);
		}
		.side-sep {
			display: none;
		}
	}
</style>
