<script lang="ts">
	import { page } from '$app/state';
	import { requestUpload, putToS3, runConvert, runDisag, runExceed } from '$lib/api';
	import type { DisagMethod, RunResult, SeasonGroup, Tool } from '$lib/types';
	import FileDrop from '$lib/FileDrop.svelte';

	const MONTH_ABBR = [
		'Jan',
		'Feb',
		'Mar',
		'Apr',
		'May',
		'Jun',
		'Jul',
		'Aug',
		'Sep',
		'Oct',
		'Nov',
		'Dec'
	];

	const VALID_TOOLS: Tool[] = ['disag', 'exceed', 'convert'];
	const queryTool = page.url.searchParams.get('tool');
	let tool = $state<Tool>(VALID_TOOLS.includes(queryTool as Tool) ? (queryTool as Tool) : 'disag');
	let method = $state<DisagMethod>(0);
	let intervals = $state(20);
	let seasonalMode = $state(false);
	let seasons = $state<SeasonGroup[]>([
		{ name: 'Wet', months: [10, 11, 12, 1, 2, 3] },
		{ name: 'Dry', months: [4, 5, 6, 7, 8, 9] }
	]);
	let monthlyFile = $state<File | null>(null);
	let daily1File = $state<File | null>(null);
	let daily2File = $state<File | null>(null);
	let ansFile = $state<File | null>(null);
	let running = $state(false);
	let result = $state<RunResult | null>(null);
	let error = $state<string | null>(null);
	let stage = $state<'idle' | 'uploading' | 'computing'>('idle');

	const methodOptions: Array<{
		value: DisagMethod;
		title: string;
		desc: string;
		needs: string;
	}> = [
		{
			value: 0,
			title: 'One file',
			desc: 'Single daily reference. Drops months that have any missing days.',
			needs: 'monthly + daily ref'
		},
		{
			value: 1,
			title: 'Patch (calendar)',
			desc: 'Backfill missing days from the closest same-calendar-month year.',
			needs: 'monthly + daily ref'
		},
		{
			value: 2,
			title: 'Patch (file)',
			desc: 'Backfill from a second daily reference whenever file 1 has a gap.',
			needs: 'monthly + 2 daily refs'
		},
		{
			value: 3,
			title: 'Incremental',
			desc: 'Pattern = file 1 − file 2, for incremental catchments below a dam.',
			needs: 'monthly + 2 daily refs'
		},
		{
			value: 4,
			title: 'Even',
			desc: 'Equal flow each day. No daily reference needed.',
			needs: 'monthly only'
		},
		{
			value: 5,
			title: 'Patch (exceedance)',
			desc: 'Cross-river percentile-match; synthesises donor months when both files lack data.',
			needs: 'monthly + 1–2 daily refs'
		}
	];

	const minFiles: Record<DisagMethod, number> = { 0: 1, 1: 1, 2: 2, 3: 2, 4: 0, 5: 1 };

	const daily1Required = $derived(tool === 'disag' && minFiles[method] >= 1);
	const daily2Visible = $derived(tool === 'disag' && (minFiles[method] >= 2 || method === 5));
	const daily2Required = $derived(tool === 'disag' && minFiles[method] >= 2);

	async function uploadIfPresent(file: File | null): Promise<string | null> {
		if (!file) return null;
		const target = await requestUpload(file.name);
		await putToS3(target, file);
		return target.key;
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		result = null;
		running = true;
		stage = 'uploading';
		try {
			if (tool === 'disag') {
				if (!monthlyFile) throw new Error('Monthly file is required.');
				if (daily1Required && !daily1File) {
					throw new Error('This method needs a daily reference file.');
				}
				if (daily2Required && !daily2File) {
					throw new Error('This method needs a second daily reference file.');
				}
				const monthly_key = (await uploadIfPresent(monthlyFile))!;
				const daily1_key = await uploadIfPresent(daily1File);
				const daily2_key = await uploadIfPresent(daily2File);
				stage = 'computing';
				result = await runDisag({ method, monthly_key, daily1_key, daily2_key });
			} else if (tool === 'exceed') {
				if (!monthlyFile && !daily1File) {
					throw new Error('Exceed needs at least one of a monthly or daily file.');
				}
				let seasonGroups: SeasonGroup[] | undefined;
				if (seasonalMode) {
					seasonGroups = seasons
						.map((s) => ({ name: s.name.trim() || 'Season', months: s.months }))
						.filter((s) => s.months.length > 0);
					if (seasonGroups.length === 0) {
						throw new Error('Add at least one season with one or more months.');
					}
				}
				const monthly_key = await uploadIfPresent(monthlyFile);
				const daily_key = await uploadIfPresent(daily1File);
				stage = 'computing';
				result = await runExceed({ monthly_key, daily_key, intervals, seasons: seasonGroups });
			} else {
				if (!ansFile) throw new Error('Source monthly file is required.');
				const ans_key = (await uploadIfPresent(ansFile))!;
				stage = 'computing';
				result = await runConvert({ ans_key });
			}
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			running = false;
			stage = 'idle';
		}
	}

	function resetForm() {
		monthlyFile = null;
		daily1File = null;
		daily2File = null;
		ansFile = null;
		result = null;
		error = null;
	}

	function outputLabel(key: string | undefined): string {
		if (!key) return 'output';
		const m = key.match(/\.([a-z0-9]+)$/i);
		if (m && m[1].toLowerCase() === 'svg') return 'curve (.svg)';
		return m ? `.${m[1].toLowerCase()} output` : 'output';
	}

	function toggleSeasonMonth(season: SeasonGroup, month: number) {
		season.months = season.months.includes(month)
			? season.months.filter((m) => m !== month)
			: [...season.months, month].sort((a, b) => a - b);
	}

	function addSeason() {
		seasons = [...seasons, { name: `Season ${seasons.length + 1}`, months: [] }];
	}

	function removeSeason(i: number) {
		seasons = seasons.filter((_, idx) => idx !== i);
	}

	const isSvg = $derived(!!result?.output_key && /\.svg$/i.test(result.output_key));
</script>

<svelte:head>
	<title>Run · Disag-MD</title>
</svelte:head>

<header class="page-head">
	<h1>Run a job</h1>
	<p>
		Upload your inputs, choose a tool and method, and submit. Files are uploaded straight to S3 from
		your browser; the run executes on AWS Lambda.
	</p>
</header>

<form onsubmit={submit} aria-busy={running}>
	<section class="card group" aria-label="Tool">
		<h2>Tool</h2>
		<div class="segmented" role="radiogroup" aria-label="Pick a tool">
			<label class:active={tool === 'disag'}>
				<input type="radio" bind:group={tool} value="disag" data-testid="tool-disag" />
				<span>Disag <small>monthly → daily</small></span>
			</label>
			<label class:active={tool === 'exceed'}>
				<input type="radio" bind:group={tool} value="exceed" data-testid="tool-exceed" />
				<span>Exceed <small>flow frequency</small></span>
			</label>
			<label class:active={tool === 'convert'}>
				<input type="radio" bind:group={tool} value="convert" data-testid="tool-convert" />
				<span>Convert <small>monthly format</small></span>
			</label>
		</div>
	</section>

	{#if tool === 'disag'}
		<section class="card group" aria-label="Method">
			<h2>Method</h2>
			<div class="method-grid">
				{#each methodOptions as opt (opt.value)}
					<label class="method-card" class:active={method === opt.value}>
						<input
							type="radio"
							bind:group={method}
							value={opt.value}
							data-testid={`method-${opt.value}`}
						/>
						<div class="method-head">
							<span class="method-num">{opt.value}</span>
							<strong>{opt.title}</strong>
						</div>
						<p>{opt.desc}</p>
						<span class="badge">{opt.needs}</span>
					</label>
				{/each}
			</div>
		</section>
	{:else if tool === 'exceed'}
		<section class="card group" aria-label="Histogram intervals">
			<h2>Histogram intervals</h2>
			<p class="muted">More intervals = finer resolution; fewer = smoother curve.</p>
			<input
				type="number"
				min="5"
				max="200"
				bind:value={intervals}
				class="input"
				data-testid="intervals-input"
			/>
		</section>

		<section class="card group" aria-label="Seasons">
			<h2>Seasons</h2>
			<label class="check">
				<input type="checkbox" bind:checked={seasonalMode} data-testid="seasonal-toggle" />
				<span>Pool months into seasons (one curve per season)</span>
			</label>
			{#if seasonalMode}
				<p class="muted">
					Throw any months together into a season — they don’t have to be contiguous.
				</p>
				<div class="seasons">
					{#each seasons as season, i (i)}
						<div class="season-row" data-testid="season-row">
							<input
								class="input season-name"
								type="text"
								bind:value={season.name}
								aria-label="Season name"
								placeholder="Season name"
							/>
							<div class="months" role="group" aria-label={`Months for ${season.name}`}>
								{#each MONTH_ABBR as label, mi (mi)}
									{@const month = mi + 1}
									<button
										type="button"
										class="month-chip"
										class:on={season.months.includes(month)}
										aria-pressed={season.months.includes(month)}
										onclick={() => toggleSeasonMonth(season, month)}
									>
										{label}
									</button>
								{/each}
							</div>
							<button
								type="button"
								class="btn ghost small"
								onclick={() => removeSeason(i)}
								disabled={seasons.length <= 1}
							>
								Remove
							</button>
						</div>
					{/each}
				</div>
				<button type="button" class="btn secondary small" onclick={addSeason}>
					+ Add season
				</button>
			{/if}
		</section>
	{/if}

	<section class="card group" aria-label="Files">
		<h2>Files</h2>
		<div class="files">
			{#if tool === 'convert'}
				<FileDrop
					label="Source monthly file (.ans)"
					accept=".ans,.ANS"
					file={ansFile}
					required={true}
					hint="Monthly file in the source modelling layout — converted to the format Disag accepts."
					testid="drop-ans"
					onchange={(f) => (ansFile = f)}
				/>
			{:else}
				<FileDrop
					label="Monthly file (.mon / .nat / .cur)"
					accept=".mon,.MON,.nat,.NAT,.cur,.CUR"
					file={monthlyFile}
					required={tool === 'disag'}
					hint="Hydro-year monthly volumes in Mm3."
					testid="drop-monthly"
					onchange={(f) => (monthlyFile = f)}
				/>
				<FileDrop
					label="Daily reference (.day)"
					accept=".day,.DAY"
					file={daily1File}
					required={daily1Required}
					hint={daily1Required
						? 'Required for this method.'
						: 'Optional for exceed and methods that don’t need a reference.'}
					testid="drop-daily1"
					onchange={(f) => (daily1File = f)}
				/>
				{#if daily2Visible}
					<FileDrop
						label="Second daily reference (.day)"
						accept=".day,.DAY"
						file={daily2File}
						required={daily2Required}
						hint={daily2Required ? 'Required for this method.' : 'Optional fallback for method 5.'}
						testid="drop-daily2"
						onchange={(f) => (daily2File = f)}
					/>
				{/if}
			{/if}
		</div>
	</section>

	<div class="actions">
		<button type="submit" class="btn" disabled={running} data-testid="submit">
			{#if running}
				<span class="spinner" aria-hidden="true"></span>
				{stage === 'uploading' ? 'Uploading…' : 'Computing on Lambda…'}
			{:else}
				Run job →
			{/if}
		</button>
		<button type="button" class="btn ghost" onclick={resetForm} disabled={running}> Reset </button>
	</div>
</form>

{#if error}
	<div class="alert error" role="alert" data-testid="run-error">
		<strong>Couldn’t run:</strong>
		<span>{error}</span>
	</div>
{/if}

{#if result}
	<div class="alert success card success-card" data-testid="run-success">
		<span class="badge success">Done</span>
		<h3>Run <code>{result.run_id}</code> complete</h3>
		<p>
			Outputs are stored in S3 under the <code>{result.tool}</code> namespace. Links below are short-lived
			(1 hour by default).
		</p>
		{#if isSvg && result.output_url}
			<figure class="curve" data-testid="curve-preview">
				<img src={result.output_url} alt="Flow-frequency exceedance curve" />
				<figcaption class="muted">
					Right-click the curve to save it, or use the button below.
				</figcaption>
			</figure>
		{/if}
		<div class="actions">
			{#if result.output_url}
				<a class="btn" href={result.output_url} data-testid="download-output">
					Download {outputLabel(result.output_key)}
				</a>
			{/if}
			<a class="btn secondary" href={result.report_url} data-testid="download-report">
				Download .rep report
			</a>
			<a class="btn ghost" href="/history">View all runs →</a>
		</div>
	</div>
{/if}

<style>
	.page-head {
		margin-bottom: var(--space-5);
	}

	form {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	/* Section labels are h2 for heading order (page h1 → section h2), but
	   sized like the compact card label they visually are, not the large
	   global h2. */
	.group h2 {
		margin-top: 0;
		font-size: 1.1rem;
	}

	.muted {
		color: var(--text-muted);
		margin: 0 0 var(--space-3);
	}

	.check {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.seasons {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		margin: var(--space-3) 0;
	}

	.season-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
	}

	.season-name {
		width: 10rem;
		flex: 0 0 auto;
	}

	.months {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.month-chip {
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text-muted);
		border-radius: var(--radius-sm);
		padding: 0.35rem 0.7rem;
		font-size: 0.8rem;
		font-weight: 500;
		cursor: pointer;
		transition:
			background 0.12s,
			border-color 0.12s,
			color 0.12s;
	}
	.month-chip:hover {
		border-color: var(--border-strong);
		color: var(--text);
	}

	.month-chip.on {
		background: var(--accent);
		border-color: var(--accent);
		color: #fff;
		font-weight: 600;
	}

	.btn.small {
		padding: 4px 10px;
		font-size: 0.85rem;
	}

	.curve {
		margin: var(--space-3) 0;
	}

	.curve img {
		width: 100%;
		max-width: 720px;
		height: auto;
		/* SVG curve is authored on a white canvas — keep it white in dark mode
		   rather than letting it sit on a dark surface. */
		background: #fff;
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
	}

	.input {
		display: inline-block;
		padding: 0.55rem 0.8rem;
		border-radius: var(--radius-md);
		border: 1px solid var(--border);
		background: var(--surface);
		width: 8rem;
		transition: border-color 0.12s;
	}
	.input:hover {
		border-color: var(--border-strong);
	}

	.segmented {
		display: inline-flex;
		background: var(--surface-2);
		padding: 4px;
		border-radius: var(--radius-md);
		gap: 4px;
	}

	.segmented label {
		display: flex;
		flex-direction: column;
		padding: 0.4rem 0.9rem;
		border-radius: calc(var(--radius-md) - 4px);
		cursor: pointer;
		color: var(--text-muted);
		min-width: 9rem;
		text-align: center;
		font-weight: 600;
		transition:
			background 0.12s,
			color 0.12s;
	}

	.segmented label.active {
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow-sm);
	}

	.segmented small {
		display: block;
		font-weight: 400;
		font-size: 0.78rem;
		color: var(--text-subtle);
		margin-top: 0.1rem;
	}

	/* Visually hidden but still keyboard-focusable and click-targetable
	   (Playwright treats `pointer-events: none` as un-actionable). */
	.segmented input {
		position: absolute;
		width: 1px;
		height: 1px;
		opacity: 0;
		margin: 0;
	}

	.method-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: var(--space-3);
	}

	.method-card {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		background: var(--surface);
		cursor: pointer;
		transition:
			border-color 0.12s,
			box-shadow 0.12s,
			transform 0.04s;
	}
	.method-card:hover {
		border-color: var(--border-strong);
	}
	.method-card.active {
		border-color: var(--accent);
		box-shadow:
			var(--shadow-sm),
			0 0 0 1px var(--accent) inset;
		background: color-mix(in srgb, var(--accent-soft) 60%, var(--surface));
	}
	.method-card input {
		position: absolute;
		width: 1px;
		height: 1px;
		opacity: 0;
		margin: 0;
	}
	.method-card p {
		font-size: 0.88rem;
		margin: 0;
		color: var(--text-muted);
	}
	.method-head {
		display: flex;
		align-items: baseline;
		gap: var(--space-2);
	}
	.method-num {
		font-family: var(--font-mono);
		font-size: 0.85rem;
		background: var(--surface-2);
		color: var(--text-muted);
		padding: 0.1rem 0.45rem;
		border-radius: var(--radius-sm);
	}

	.files {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: var(--space-3);
	}

	.actions {
		display: flex;
		gap: var(--space-3);
		align-items: center;
		flex-wrap: wrap;
	}

	.spinner {
		width: 14px;
		height: 14px;
		border: 2px solid currentColor;
		border-bottom-color: transparent;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.success-card {
		flex-direction: column;
		align-items: stretch;
		margin-top: var(--space-5);
	}
	.success-card h3 {
		margin: var(--space-2) 0;
	}
</style>
