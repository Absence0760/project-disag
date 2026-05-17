<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';

	let { children } = $props();

	const nav = [
		{ href: '/', label: 'Overview' },
		{ href: '/run', label: 'Run' },
		{ href: '/history', label: 'History' }
	];
</script>

<a class="sr-only" href="#main">Skip to content</a>

<header class="site-header">
	<div class="brand">
		<svg class="logo" viewBox="0 0 64 64" aria-hidden="true">
			<rect width="64" height="64" rx="14" fill="currentColor" />
			<path
				fill="none"
				stroke="white"
				stroke-width="4"
				stroke-linecap="round"
				d="M10 42c8 0 8-12 16-12s8 12 16 12 8-12 16-12"
			/>
		</svg>
		<a href="/" class="brand-link">
			<span class="brand-name">Disag-MD</span>
			<span class="brand-tag">hydrology toolkit</span>
		</a>
	</div>

	<nav aria-label="Primary">
		{#each nav as item (item.href)}
			<a
				href={item.href}
				class:active={$page.url.pathname === item.href ||
					(item.href !== '/' && $page.url.pathname.startsWith(item.href))}
				data-testid={`nav-${item.href === '/' ? 'home' : item.href.slice(1)}`}
			>
				{item.label}
			</a>
		{/each}
	</nav>
</header>

<main id="main">
	{@render children()}
</main>

<footer class="site-footer">
	<div class="footer-inner">
		<span> Python port of the 1991 Disag-MD Pascal tool (AJ Greyling; H Beuster 2007). </span>
		<span class="muted">
			<a href="https://github.com/jaredhoward" rel="noopener">Source</a>
			· pure stdlib · AWS Lambda
		</span>
	</div>
</footer>

<style>
	.site-header {
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-5);
		padding: var(--space-4) clamp(var(--space-4), 5vw, var(--space-8));
		background: color-mix(in srgb, var(--surface) 85%, transparent);
		backdrop-filter: saturate(140%) blur(10px);
		border-bottom: 1px solid var(--border);
	}

	.brand {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		color: var(--accent);
	}

	.logo {
		width: 36px;
		height: 36px;
	}

	.brand-link {
		display: flex;
		flex-direction: column;
		text-decoration: none;
		line-height: 1.1;
		color: inherit;
	}
	.brand-link:hover {
		text-decoration: none;
	}

	.brand-name {
		font-weight: 700;
		color: var(--text);
		letter-spacing: -0.01em;
	}

	.brand-tag {
		font-size: 0.78rem;
		color: var(--text-subtle);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	nav {
		display: flex;
		gap: var(--space-1);
	}

	nav a {
		padding: 0.4rem 0.85rem;
		border-radius: var(--radius-md);
		color: var(--text-muted);
		font-weight: 500;
		font-size: 0.94rem;
		transition:
			color 0.12s,
			background 0.12s;
	}
	nav a:hover {
		color: var(--text);
		background: var(--surface-2);
		text-decoration: none;
	}
	nav a.active {
		color: var(--accent);
		background: var(--accent-soft);
	}

	main {
		max-width: 1040px;
		margin: 0 auto;
		padding: clamp(var(--space-5), 4vw, var(--space-8)) clamp(var(--space-4), 5vw, var(--space-8));
		min-height: calc(100vh - 200px);
	}

	.site-footer {
		border-top: 1px solid var(--border);
		padding: var(--space-5) clamp(var(--space-4), 5vw, var(--space-8));
		color: var(--text-subtle);
		font-size: 0.88rem;
	}

	.footer-inner {
		max-width: 1040px;
		margin: 0 auto;
		display: flex;
		justify-content: space-between;
		gap: var(--space-4);
		flex-wrap: wrap;
	}

	.muted {
		color: var(--text-subtle);
	}

	@media (max-width: 600px) {
		.brand-tag {
			display: none;
		}
		nav a {
			padding: 0.4rem 0.6rem;
			font-size: 0.88rem;
		}
	}
</style>
