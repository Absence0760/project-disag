<script lang="ts">
	const features = [
		{
			title: 'Run a disaggregation',
			body: 'Upload a monthly streamflow file and pick one of six methods. Get a daily output and an audit report.',
			href: '/run',
			cta: 'Start a run'
		},
		{
			title: 'Browse past runs',
			body: 'Inputs and outputs are kept in S3. Reopen any run, re-download the .day output, or grab the .rep report.',
			href: '/history',
			cta: 'Open history'
		}
	];

	const stats = [
		{ label: 'Methods', value: '6' },
		{ label: 'Runtime', value: 'AWS Lambda' },
		{ label: 'Compute', value: 'arm64 · 4 GB' },
		{ label: 'Storage', value: 'S3 (versioned)' }
	];
</script>

<svelte:head>
	<title>Disag-MD — hydrology toolkit</title>
</svelte:head>

<section class="hero">
	<span class="badge" data-testid="hero-badge">Live · serverless</span>
	<h1>Disaggregate monthly streamflow into daily flow.</h1>
	<p class="lede">
		A Python port of the 1991 Disag-MD Pascal tool, on the web. Upload your monthly volumes, choose
		from six disaggregation methods, and get back a usable daily series with a full audit trail.
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

<section class="features" aria-label="What you can do">
	{#each features as feature (feature.href)}
		<a
			class="card feature-card"
			href={feature.href}
			data-testid={`feature-${feature.href.slice(1)}`}
		>
			<h3>{feature.title}</h3>
			<p>{feature.body}</p>
			<span class="cta">{feature.cta} →</span>
		</a>
	{/each}
</section>

<section class="methods" aria-label="Disaggregation methods">
	<h2>Six methods</h2>
	<p class="lede-sm">
		Pick the cheapest method that still gives you a usable signal. Method 0 is the baseline; later
		methods patch missing days from reference rivers.
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

	.features {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: var(--space-4);
		margin: var(--space-6) 0;
	}

	.feature-card {
		text-decoration: none;
		color: inherit;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		transition:
			transform 0.12s ease,
			box-shadow 0.16s ease,
			border-color 0.12s;
	}

	.feature-card:hover {
		transform: translateY(-2px);
		box-shadow: var(--shadow-md);
		border-color: var(--border-strong);
		text-decoration: none;
	}

	.feature-card .cta {
		color: var(--accent);
		font-weight: 600;
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
