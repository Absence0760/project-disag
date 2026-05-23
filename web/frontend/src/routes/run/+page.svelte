<script lang="ts">
	import { page } from '$app/state';
	import { requestUpload, putToS3, runDisag, runExceed } from '$lib/api';
	import type { DisagMethod, RunResult } from '$lib/types';
	import FileDrop from '$lib/FileDrop.svelte';

	type Tool = 'disag' | 'exceed';

	let tool = $state<Tool>(page.url.searchParams.get('tool') === 'exceed' ? 'exceed' : 'disag');
	let method = $state<DisagMethod>(0);
	let intervals = $state(20);
	let monthlyFile = $state<File | null>(null);
	let daily1File = $state<File | null>(null);
	let daily2File = $state<File | null>(null);
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
			} else {
				if (!monthlyFile && !daily1File) {
					throw new Error('Exceed needs at least one of a monthly or daily file.');
				}
				const monthly_key = await uploadIfPresent(monthlyFile);
				const daily_key = await uploadIfPresent(daily1File);
				stage = 'computing';
				result = await runExceed({ monthly_key, daily_key, intervals });
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
		result = null;
		error = null;
	}
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
		<h3>Tool</h3>
		<div class="segmented" role="radiogroup" aria-label="Pick a tool">
			<label class:active={tool === 'disag'}>
				<input type="radio" bind:group={tool} value="disag" data-testid="tool-disag" />
				<span>Disag <small>monthly → daily</small></span>
			</label>
			<label class:active={tool === 'exceed'}>
				<input type="radio" bind:group={tool} value="exceed" data-testid="tool-exceed" />
				<span>Exceed <small>flow frequency</small></span>
			</label>
		</div>
	</section>

	{#if tool === 'disag'}
		<section class="card group" aria-label="Method">
			<h3>Method</h3>
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
	{:else}
		<section class="card group" aria-label="Histogram intervals">
			<h3>Histogram intervals</h3>
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
	{/if}

	<section class="card group" aria-label="Files">
		<h3>Files</h3>
		<div class="files">
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
		<div class="actions">
			{#if result.output_url}
				<a class="btn" href={result.output_url} data-testid="download-output">
					Download .day output
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

	.group h3 {
		margin-top: 0;
	}

	.muted {
		color: var(--text-muted);
		margin: 0 0 var(--space-3);
	}

	.input {
		display: inline-block;
		padding: 0.55rem 0.8rem;
		border-radius: var(--radius-md);
		border: 1px solid var(--border);
		background: var(--surface);
		width: 8rem;
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
