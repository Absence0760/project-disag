<script lang="ts">
	type ToolCard = {
		id: 'disag' | 'exceed' | 'converter';
		title: string;
		tagline: string;
		body: string;
		bullets: string[];
		href: string;
		cta: string;
	};

	const tools: ToolCard[] = [
		{
			id: 'disag',
			title: 'Disag',
			tagline: 'Monthly → daily',
			body: 'Disaggregate a monthly streamflow series into a daily series. Six methods, from a one-file baseline through cross-river percentile matching when both reference rivers have gaps.',
			bullets: [
				'Inputs: a monthly file plus 0–2 daily reference files',
				'Outputs: a daily series plus a report showing every patch and fallback',
				'Best for: turning a monthly volume record into a usable daily series for downstream modelling'
			],
			href: '/run?tool=disag',
			cta: 'Open Disag'
		},
		{
			id: 'exceed',
			title: 'Exceed',
			tagline: 'Flow-frequency analysis',
			body: 'Compute the exceedance (percentile) distribution for monthly or daily flow data. Produces a separate curve for each of the twelve calendar months, with optional seasonal grouping and monthly↔daily matching.',
			bullets: [
				'Inputs: a monthly file and/or a daily file (either alone works)',
				'Outputs: a report listing flow values at each exceedance bin per month or season',
				'Best for: comparing wet vs. dry-season frequency, or sanity-checking a disagged daily series against its source monthly'
			],
			href: '/run?tool=exceed',
			cta: 'Open Exceed'
		},
		{
			id: 'converter',
			title: 'Converter',
			tagline: 'Monthly format converter',
			body: 'Convert a monthly streamflow file from the source modelling layout into the format Disag accepts. Also wired into the desktop Disag GUI as a "Convert…" button.',
			bullets: [
				'Inputs: a monthly streamflow file in the source layout',
				'Outputs: a monthly file in the format Disag reads',
				'Best for: bringing in a monthly record produced by another tool without retyping it'
			],
			href: '/run?tool=convert',
			cta: 'Open Converter'
		}
	];

	const stats = [
		{ label: 'Tools', value: '3' },
		{ label: 'Disag methods', value: '6' },
		{ label: 'Runtime', value: 'AWS Lambda' },
		{ label: 'Dependencies', value: 'Python stdlib' }
	];
</script>

<svelte:head>
	<title>Disag-MD — hydrology toolkit</title>
</svelte:head>

<section class="hero">
	<span class="badge" data-testid="hero-badge">Live · serverless</span>
	<h1>Disaggregate, profile, and convert monthly streamflow data.</h1>
	<p class="lede">
		A web port of the 1991 Disag-MD Pascal toolkit (AJ Greyling; H Beuster 2007). Three tools share
		one set of file readers and one Lambda backend — pick the one that fits the question you're
		asking.
	</p>

	<div class="hero-cta">
		<a class="btn" href="/run" data-testid="hero-primary">Start a run →</a>
		<a class="btn ghost" href="/history" data-testid="hero-secondary">View previous runs</a>
	</div>

	<dl class="stats" aria-label="System overview">
		{#each stats as stat (stat.label)}
			<div>
				<dt>{stat.label}</dt>
				<dd>{stat.value}</dd>
			</div>
		{/each}
	</dl>
</section>

<section class="tools" aria-label="Tools in the toolkit">
	<h2>The three tools</h2>
	<div class="tool-grid">
		{#each tools as t (t.id)}
			<article class="card tool-card" data-testid={`feature-${t.id}`}>
				<header>
					<h3>{t.title}</h3>
					<span class="tagline">{t.tagline}</span>
				</header>
				<p>{t.body}</p>
				<ul>
					{#each t.bullets as b (b)}
						<li>{b}</li>
					{/each}
				</ul>
				<div class="tool-cta">
					<a class="btn" href={t.href} data-testid={`feature-${t.id}-cta`}>{t.cta} →</a>
				</div>
			</article>
		{/each}
	</div>
</section>

<section class="methods" aria-label="Disaggregation methods">
	<h2>Disag's six methods</h2>
	<p class="lede-sm">
		Pick the cheapest method that still gives you a usable signal. Method 0 is the baseline; later
		methods patch missing days from reference rivers or synthesised donors.
	</p>
	<ol class="method-list">
		<li><strong>0 · One file</strong> — single daily reference, drop incomplete months.</li>
		<li>
			<strong>1 · Patch (calendar)</strong> — backfill from the closest same-calendar-month year.
		</li>
		<li><strong>2 · Patch (file)</strong> — backfill from a second daily reference.</li>
		<li>
			<strong>3 · Incremental</strong> — pattern from <code>file1 − file2</code> for incremental catchments.
		</li>
		<li><strong>4 · Even</strong> — equal flow per day; no daily reference needed.</li>
		<li>
			<strong>5 · Patch (exceedance)</strong> — cross-river percentile match for synthetic donor months.
		</li>
	</ol>
</section>

<style>
	.hero {
		padding: var(--space-6) 0 var(--space-8);
		max-width: 760px;
	}

	.hero h1 {
		margin-top: var(--space-3);
	}

	.lede {
		font-size: 1.1rem;
		color: var(--text-muted);
		max-width: 640px;
	}

	.lede-sm {
		color: var(--text-muted);
	}

	.hero-cta {
		display: flex;
		gap: var(--space-3);
		flex-wrap: wrap;
		margin: var(--space-5) 0;
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: var(--space-4);
		margin: var(--space-6) 0 0;
		padding: 0;
	}

	.stats > div {
		border-left: 2px solid var(--accent);
		padding-left: var(--space-3);
	}

	.stats dt {
		font-size: 0.78rem;
		color: var(--text-subtle);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.stats dd {
		margin: 0.2rem 0 0;
		font-size: 1.05rem;
		font-weight: 600;
		color: var(--text);
	}

	.tools {
		margin: var(--space-8) 0;
	}

	.tool-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: var(--space-4);
		margin-top: var(--space-4);
		align-items: stretch;
	}

	.tool-card {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.tool-card header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--space-2);
		flex-wrap: wrap;
	}

	.tool-card h3 {
		margin: 0;
	}

	.tagline {
		color: var(--text-subtle);
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.tool-card ul {
		padding-left: 1.1rem;
		margin: 0;
		color: var(--text-muted);
		font-size: 0.94rem;
	}

	.tool-card ul li + li {
		margin-top: 0.3rem;
	}

	.tool-cta {
		margin-top: auto;
	}

	.methods {
		margin-top: var(--space-8);
	}

	.method-list {
		list-style: none;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: var(--space-3);
		margin-top: var(--space-4);
	}

	.method-list li {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: var(--space-3) var(--space-4);
		color: var(--text-muted);
	}
	.method-list strong {
		color: var(--text);
	}
</style>
