<script lang="ts">
	import { onMount } from 'svelte';
	import { listRuns } from '$lib/api';
	import type { RunSummary } from '$lib/types';

	let runs = $state<RunSummary[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			runs = await listRuns();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	});

	function fmtSize(b: number): string {
		if (b < 1024) return `${b} B`;
		if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
		return `${(b / 1024 / 1024).toFixed(2)} MB`;
	}

	function fmtDate(iso: string): string {
		return new Date(iso).toLocaleString(undefined, {
			year: 'numeric',
			month: 'short',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

<svelte:head>
	<title>History · Disag-MD</title>
</svelte:head>

<header class="page-head">
	<h1>Previous runs</h1>
	<p>
		All runs are stored in S3 under <code>runs/&lt;tool&gt;/&lt;id&gt;/</code>. Newest first.
	</p>
</header>

{#if loading}
	<div class="card" data-testid="history-loading" aria-busy="true">
		{#each Array(3) as _, i (i)}
			<div class="skeleton-row">
				<div class="skel skel-id"></div>
				<div class="skel skel-tool"></div>
				<div class="skel skel-date"></div>
				<div class="skel skel-size"></div>
			</div>
		{/each}
		<span class="sr-only">Loading runs…</span>
	</div>
{:else if error}
	<div class="alert error" role="alert" data-testid="history-error">
		<div>
			<strong>Couldn’t load history.</strong>
			<p>{error}</p>
		</div>
	</div>
{:else if runs.length === 0}
	<div class="card empty" data-testid="history-empty">
		<svg viewBox="0 0 24 24" width="42" height="42" aria-hidden="true">
			<path
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M3 6h18M6 6v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6M9 11v5M15 11v5"
			/>
		</svg>
		<div>
			<h3>No runs yet</h3>
			<p>Submit your first disaggregation or exceedance job to see it here.</p>
			<a class="btn" href="/run">Start a run →</a>
		</div>
	</div>
{:else}
	<div class="card no-pad" data-testid="history-list">
		<table>
			<thead>
				<tr>
					<th scope="col">Run</th>
					<th scope="col">Tool</th>
					<th scope="col">Created</th>
					<th scope="col" class="num">Size</th>
					<th scope="col" class="sr-only">Action</th>
				</tr>
			</thead>
			<tbody>
				{#each runs as run (run.run_id)}
					<tr>
						<td><code>{run.run_id}</code></td>
						<td><span class="badge">{run.tool}</span></td>
						<td class="muted">{fmtDate(run.created_at)}</td>
						<td class="num muted">{fmtSize(run.size_bytes)}</td>
						<td class="row-cta">
							<a class="btn secondary" href={`/run/${run.run_id}`}>Open →</a>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	.page-head {
		margin-bottom: var(--space-5);
	}
	.no-pad {
		padding: 0;
		overflow: hidden;
	}

	table {
		width: 100%;
		border-collapse: collapse;
	}

	th,
	td {
		padding: var(--space-3) var(--space-4);
		text-align: left;
		border-bottom: 1px solid var(--border);
	}
	tbody tr:last-child td {
		border-bottom: none;
	}
	tbody tr:hover {
		background: var(--surface-2);
	}

	th {
		font-size: 0.78rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-subtle);
		background: var(--surface-2);
	}

	td.muted {
		color: var(--text-muted);
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.row-cta {
		text-align: right;
	}

	.skeleton-row {
		display: grid;
		grid-template-columns: 2fr 1fr 2fr 1fr;
		gap: var(--space-3);
		padding: var(--space-3) 0;
		border-bottom: 1px solid var(--border);
	}
	.skeleton-row:last-child {
		border: none;
	}

	.skel {
		height: 12px;
		border-radius: var(--radius-sm);
		background: linear-gradient(
			90deg,
			var(--surface-2) 0%,
			color-mix(in srgb, var(--surface-2) 70%, var(--border-strong)) 50%,
			var(--surface-2) 100%
		);
		background-size: 200% 100%;
		animation: shimmer 1.4s infinite;
	}

	@keyframes shimmer {
		0% {
			background-position: 200% 0;
		}
		100% {
			background-position: -200% 0;
		}
	}

	.empty {
		display: flex;
		align-items: flex-start;
		gap: var(--space-4);
		color: var(--text-muted);
	}
	.empty svg {
		color: var(--accent);
		flex: none;
	}
	.empty h3 {
		margin-top: 0;
		color: var(--text);
	}
</style>
